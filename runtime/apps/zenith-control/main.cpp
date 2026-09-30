#include <atomic>
#include <chrono>
#include <exception>
#include <iostream>
#include <string_view>
#include <thread>

#include <sys/utsname.h>

namespace {
void print_version()
{
    std::cout << "zenith-control " << ZENITH_VERSION
              << " platform=" << ZENITH_PLATFORM
              << " compiler=" << ZENITH_COMPILER << '\n';
}

int self_check()
{
    utsname system{};
    if (uname(&system) != 0) {
        std::cerr << "self-check: uname failed\n";
        return 1;
    }

    const auto before = std::chrono::steady_clock::now();
    std::atomic<bool> worker_completed{false};
    std::jthread worker([&worker_completed] { worker_completed.store(true); });
    worker.join();
    const auto after = std::chrono::steady_clock::now();
    if (!worker_completed.load() || after < before) {
        std::cerr << "self-check: thread or monotonic clock failed\n";
        return 1;
    }

    print_version();
    std::cout << "system=" << system.sysname << " kernel=" << system.release
              << " machine=" << system.machine << '\n'
              << "self-check: ok (C++20 thread and monotonic clock)\n";
    return 0;
}
} // namespace

int main(int argc, char* argv[])
{
    try {
        if (argc == 1 || (argc == 2 && std::string_view(argv[1]) == "--self-check")) {
            return self_check();
        }
        if (argc == 2 && std::string_view(argv[1]) == "--version") {
            print_version();
            return 0;
        }
        if (argc == 2 && std::string_view(argv[1]) == "--help") {
            std::cout << "Usage: zenith-control [--self-check|--version|--help]\n";
            return 0;
        }
        std::cerr << "Invalid arguments; use --help\n";
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "Runtime check failed: " << error.what() << '\n';
        return 1;
    }
}
