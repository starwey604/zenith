// SPDX-License-Identifier: BSD-3-Clause
#include "amp_uio.hpp"
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>

static std::string read_text(const std::filesystem::path &p) {
    std::ifstream f(p); std::string s;
    if (!std::getline(f, s)) throw std::runtime_error("cannot read " + p.string());
    return s;
}
AmpUio::AmpUio(const std::string &requested)
{
    if (sysconf(_SC_PAGESIZE) != 4096) throw std::runtime_error("v1 requires 4 KiB pages");
    path = requested;
    if (path.empty()) {
        for (const auto &e : std::filesystem::directory_iterator("/sys/class/uio")) {
            if (read_text(e.path() / "name") == "zenith-amp-shm") {
                if (!path.empty()) throw std::runtime_error("multiple AMP devices: specify --device");
                path = "/dev/" + e.path().filename().string();
            }
        }
    }
    if (path.empty()) throw std::runtime_error("zenith-amp-shm UIO device not found");
    auto sys = std::filesystem::path("/sys/class/uio") / std::filesystem::path(path).filename();
    if (read_text(sys / "name") != "zenith-amp-shm" || read_text(sys / "version") != "1")
        throw std::runtime_error("unexpected UIO device/version");
    if (std::stoull(read_text(sys / "maps/map0/size"), nullptr, 0) != AMP_HOST_OFFSET ||
        std::stoull(read_text(sys / "maps/map1/size"), nullptr, 0) != AMP_WINDOW_SIZE - AMP_HOST_OFFSET)
        throw std::runtime_error("unexpected UIO map sizes");
    fd = open(path.c_str(), O_RDWR | O_CLOEXEC);
    if (fd < 0) throw std::runtime_error("open " + path + ": " + std::strerror(errno));
    void *a = mmap(nullptr, AMP_HOST_OFFSET, PROT_READ, MAP_SHARED, fd, 0);
    if (a == MAP_FAILED) { close(fd); fd = -1; throw std::runtime_error("mmap data failed"); }
    void *b = mmap(nullptr, AMP_WINDOW_SIZE - AMP_HOST_OFFSET, PROT_READ | PROT_WRITE,
                   MAP_SHARED, fd, 4096);
    if (b == MAP_FAILED) { munmap(a, AMP_HOST_OFFSET); close(fd); fd = -1; throw std::runtime_error("mmap control failed"); }
    device = static_cast<const amp_device *>(a); host = static_cast<amp_host *>(b);
    if (std::filesystem::exists(sys / "maps/map2")) {
        bool valid = read_text(sys / "maps/map2/name") == "m0-clock-ro" &&
            std::stoull(read_text(sys / "maps/map2/size"), nullptr, 0) == 4096;
        void *c = valid ? mmap(nullptr, 4096, PROT_READ, MAP_SHARED, fd, 8192) : MAP_FAILED;
        if (c == MAP_FAILED) {
            munmap(a, AMP_HOST_OFFSET); munmap(b, AMP_WINDOW_SIZE - AMP_HOST_OFFSET);
            close(fd); throw std::runtime_error("invalid clock map");
        }
        clock = static_cast<const volatile uint32_t *>(c);
    }
}
AmpUio::~AmpUio() {
    if (device) munmap(const_cast<amp_device *>(device), AMP_HOST_OFFSET);
    if (host) munmap(host, AMP_WINDOW_SIZE - AMP_HOST_OFFSET);
    if (clock) munmap(const_cast<uint32_t *>(clock), 4096);
    if (fd >= 0) close(fd);
}
void AmpUio::check_protection() const
{
    auto reject = [&](size_t size, int prot, int flags, off_t offset) {
        void *p = mmap(nullptr, size, prot, flags, fd, offset);
        if (p != MAP_FAILED) { munmap(p, size); throw std::runtime_error("unsafe mapping accepted"); }
    };
    reject(4096, PROT_READ | PROT_WRITE, MAP_SHARED, 0);
    reject(AMP_HOST_OFFSET + 4096, PROT_READ, MAP_SHARED, 0);
    reject(4096, PROT_READ, MAP_SHARED, clock ? 12288 : 8192);
    if (clock) {
        reject(4096, PROT_READ | PROT_WRITE, MAP_SHARED, 8192);
        reject(8192, PROT_READ, MAP_SHARED, 8192);
        reject(4096, PROT_READ | PROT_EXEC, MAP_SHARED, 8192);
        if (!mprotect(const_cast<uint32_t *>(clock), 4096, PROT_READ | PROT_WRITE))
            throw std::runtime_error("clock could be made writable");
    }
    reject(4096, PROT_READ, MAP_PRIVATE, 0);
    reject(4096, PROT_READ | PROT_EXEC, MAP_SHARED, 0);
    if (!mprotect(const_cast<amp_device *>(device), 4096, PROT_READ | PROT_WRITE))
        throw std::runtime_error("read-only data could be made writable");
    int other = open(path.c_str(), O_RDWR | O_CLOEXEC);
    if (other >= 0) { close(other); throw std::runtime_error("second owner accepted"); }
    if (errno != EBUSY) throw std::runtime_error("second open failed for unexpected reason");
}

uint64_t AmpUio::clock_ticks() const {
    if (!clock) throw std::runtime_error("TIMER11 read-only map required for CAN comparison");
    uint32_t high, low, again;
    amp_fence();
    do { high = clock[3]; low = clock[2]; again = clock[3]; } while (high != again);
    amp_fence();
    uint64_t count = (uint64_t(high) << 32) | low;
    return count >> 62 ? ~count : count; // Same convention as HAL_GetSysTimerCount.
}
