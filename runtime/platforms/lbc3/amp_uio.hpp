// SPDX-License-Identifier: BSD-3-Clause
#pragma once
#include "amp_shm.h"
#include <string>
class AmpUio {
public:
    explicit AmpUio(const std::string &path = {});
    ~AmpUio();
    AmpUio(const AmpUio &) = delete;
    AmpUio &operator=(const AmpUio &) = delete;
    const amp_device *device = nullptr;
    amp_host *host = nullptr;
    void check_protection() const;
    uint64_t clock_ticks() const;
    const volatile uint32_t *clock = nullptr;
    std::string path;
private:
    int fd = -1;
};
