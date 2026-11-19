// SPDX-License-Identifier: BSD-3-Clause
#include "amp_uio.hpp"
#include "m0_idle.hpp"
#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>

using Clock = std::chrono::steady_clock;
using namespace std::chrono_literals;

class Console {
    AmpUio map;
    const m0dbg_info *p;
    m0dbg_cmd *cmd;
    const char *ring;
    uint32_t boot;
    void check_boot() const {
        if (amp_load(&p->magic) != M0DBG_MAGIC)
            throw std::runtime_error("M0 debug firmware not present");
        if (amp_load(&p->boot) != boot)
            throw std::runtime_error("M0 restarted; reconnect");
    }
    // Copy before checking revision again. Do not emit a torn chunk on wrap.
    void drain(uint32_t &cursor, bool history = false) const {
        std::array<char, M0DBG_BYTES> copy;
        const auto until = Clock::now() + 2s;
        do {
            check_boot();
            const uint32_t rev = amp_load(&p->revision);
            if (!(rev & 1)) {
                uint32_t end = amp_load(&p->end);
                uint32_t kept = std::min(amp_load(&p->kept), M0DBG_BYTES);
                uint32_t available = history ? kept : end - cursor;
                uint32_t n = std::min(available, kept);
                uint32_t lost = history ? amp_load(&p->evicted) : available - n;
                uint32_t pos = (end - n) % M0DBG_BYTES;
                uint32_t first = std::min(n, M0DBG_BYTES - pos);
                if (first) std::memcpy(copy.data(), ring + pos, first);
                if (n > first) std::memcpy(copy.data() + first, ring, n - first);
                if (amp_load(&p->revision) == rev) {
                    check_boot();
                    if (lost) std::fprintf(stderr, "m0ctl: %u older log bytes overwritten\n", lost);
                    if (n && (std::fwrite(copy.data(), 1, n, stdout) != n || std::fflush(stdout)))
                        throw std::runtime_error("cannot write logs");
                    cursor = end;
                    return;
                }
            }
            std::this_thread::sleep_for(1ms);
        } while (Clock::now() < until);
        throw std::runtime_error("M0 log buffer did not finish publishing");
    }
public:
    Console() {
        auto *ro = reinterpret_cast<const char *>(map.device);
        auto *rw = reinterpret_cast<char *>(map.host);
        p = reinterpret_cast<const m0dbg_info *>(ro + M0DBG_INFO);
        cmd = reinterpret_cast<m0dbg_cmd *>(rw + M0DBG_CMD);
        ring = rw + M0DBG_LOG;
        boot = amp_load(&p->boot);
        check_boot();
    }
    void logs(bool follow) const {
        uint32_t cursor = 0;
        drain(cursor, true);
        while (follow) {
            std::this_thread::sleep_for(20ms);
            drain(cursor);
        }
    }
    int run(const std::string &line, unsigned seconds) {
        if (!amp_load(&p->ready)) throw std::runtime_error("M0 command thread not ready");
        uint32_t req = amp_load(&cmd->request);
        if (req != amp_load(&p->ack)) throw std::runtime_error("previous M0 command still pending; use logs -f");
        uint32_t cursor = amp_load(&p->end);
        ++req;
        std::memcpy(cmd->line, line.c_str(), line.size() + 1);
        amp_store(&cmd->boot, boot);
        amp_store(&cmd->request, req);
        auto until = Clock::now() + std::chrono::seconds(seconds);
        for (;;) {
            check_boot();
            if (amp_load(&p->ack) == req) {
                int rc = p->result;
                drain(cursor);
                std::fprintf(stderr, "m0ctl: MSH exit %d\n", rc);
                return rc < 0 || rc > 255 ? 1 : rc;
            }
            drain(cursor);
            if (Clock::now() >= until) throw std::runtime_error("timeout; command was not cancelled");
            std::this_thread::sleep_for(10ms);
        }
    }
};

// The deployer also runs against the previous (pre-console) SDK firmware.
static void check_idle() {
    AmpUio map;
    auto *ro = reinterpret_cast<const char *>(map.device);
    auto *rw = reinterpret_cast<const char *>(map.host);
    auto *p = reinterpret_cast<const m0dbg_info *>(ro + M0DBG_INFO);
    auto *cmd = reinterpret_cast<const m0dbg_cmd *>(rw + M0DBG_CMD);
    if (!m0_producer_idle(map.device, p))
        throw std::runtime_error("M0 tests not idle or unexpected firmware");
    if (amp_load(&p->magic) == M0DBG_MAGIC && amp_load(&cmd->request) != amp_load(&p->ack))
        throw std::runtime_error("M0 command still pending");
}

int main(int argc, char **argv) {
    try {
        std::string op = argc > 1 ? argv[1] : "";
        if (op == "check-idle" && argc == 2) { check_idle(); return 0; }
        if (op == "logs" && (argc == 2 || (argc == 3 && std::string(argv[2]) == "-f"))) {
            Console().logs(argc == 3);
            return 0;
        }
        if (op == "run" && argc > 2) {
            int i = 2; unsigned seconds = 30;
            if (std::string(argv[i]) == "--timeout") {
                if (argc < 5) throw std::runtime_error("run --timeout SECONDS COMMAND");
                std::string value = argv[++i];
                auto [end, ec] = std::from_chars(value.data(), value.data()+value.size(), seconds);
                if (ec != std::errc() || end != value.data()+value.size() || !seconds)
                    throw std::runtime_error("invalid timeout");
                ++i;
            }
            std::string line;
            for (; i < argc; ++i) {
                if (!line.empty()) line += ' ';
                line += argv[i];
            }
            if (line.find_first_not_of(" \t") == std::string::npos ||
                line.size() >= M0DBG_LINE || line.find_first_of("\r\n") != std::string::npos)
                throw std::runtime_error("expected one MSH line of 1..79 bytes");
            return Console().run(line, seconds);
        }
        std::fprintf(stderr, "usage: m0ctl run [--timeout SEC] COMMAND [ARGS...] | logs [-f]\n");
        return 2;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "m0ctl: %s\n", e.what());
        return 1;
    }
}
