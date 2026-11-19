// One live viewer owns UIO. SSH stdin carries its heartbeat even with UDP data.
#pragma once
#include <arpa/inet.h>
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <sstream>

static int live_view(const char *transport, unsigned port, unsigned hz, const m0dbg_info *dbg,
                     m0dbg_cmd *cmd, const imu_channel *ch, imu_reader *ctrl, const rpshm_latest_rx &rx,
                     uint32_t boot, uint32_t req) {
    const bool udp = std::string(transport) == "udp";
    if ((!udp && (std::string(transport) != "ssh" || port)) || (udp && (!port || port > 65535)))
        throw std::runtime_error("live: use ssh 0 or udp PORT");
    int fd = -1;
    if (udp) {
        std::string peer;
        const char *env = getenv("SSH_CONNECTION");
        std::istringstream{env ? env : ""} >> peer;
        sockaddr_in dest{};
        dest.sin_family = AF_INET;
        dest.sin_port = htons(port);
        if (inet_pton(AF_INET, peer.c_str(), &dest.sin_addr) != 1)
            throw std::runtime_error("UDP requires a direct IPv4 SSH session");
        fd = socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC, 0);
        if (fd < 0 || connect(fd, (sockaddr *)&dest, sizeof dest))
            throw std::runtime_error("UDP socket");
    }
    signal(SIGPIPE, SIG_IGN);
    uint32_t session = ++req ? req : 1;
    amp_store(&ctrl->reading, 0);
    amp_store(&ctrl->live_session, session);
    amp_store(&ctrl->heartbeat, 1);
    struct Stop {
        imu_reader *p;
        ~Stop() { amp_store(&p->live_session, 0); }
    } stop{ctrl};
    snprintf(cmd->line, sizeof(cmd->line), "icm45686 live_irq %u 0 %u", hz, session);
    amp_store(&cmd->boot, boot);
    amp_store(&cmd->request, req);
    // Session ID authenticates frame continuity across reconnects, not network peers.
    printf("START %u\n", session);
    fflush(stdout);
    uint64_t started = ns(), next = started, contact = started;
    uint32_t beat = 1;
    bool saw = false;
    for (;;) {
        pollfd pfd{STDIN_FILENO, POLLIN, 0};
        if (poll(&pfd, 1, 0) > 0 && pfd.revents) {
            char bytes[64];
            if (read(STDIN_FILENO, bytes, sizeof(bytes)) <= 0)
                break;
            contact = ns();
            amp_store(&ctrl->heartbeat, ++beat);
        }
        auto now = ns();
        if (now - contact > 5000000000ull)
            break;
        if (amp_load(&dbg->boot) != boot)
            throw std::runtime_error("M0 restarted");
        if (amp_load(&dbg->ack) == req)
            throw std::runtime_error("IMU stopped; keep still during startup; see m0ctl logs");
        if (!saw && now - started > 6500000000ull)
            throw std::runtime_error("no calibrated pose");
        if (amp_load(&ch->ready.v) == session) {
            imu_pose f;
            rpshm_latest_read(&rx, &f);
            if (f.valid && f.session == session && f.seq) {
                char line[176];
                int len = snprintf(line, sizeof(line), "Q %u %u %llu %.9g %.9g %.9g %.9g\n", session, f.seq,
                                   (unsigned long long)f.observed, f.q[0], f.q[1], f.q[2], f.q[3]);
                if (udp) {
                    if (send(fd, line, len, MSG_DONTWAIT) < 0 && errno != EAGAIN && errno != EWOULDBLOCK)
                        throw std::runtime_error("UDP send failed");
                } else if (write(STDOUT_FILENO, line, len) != len)
                    break;
                saw = true;
            }
        }
        next += 4000000;
        now = ns();
        if (next < now)
            next += ((now - next) / 4000000 + 1) * 4000000;
        until(next);
    }
    amp_store(&ctrl->live_session, 0);
    auto end = ns() + 1500000000ull;
    while (amp_load(&dbg->ack) != req && ns() < end)
        usleep(10000);
    if (fd >= 0)
        close(fd);
    if (amp_load(&dbg->ack) != req || dbg->result)
        throw std::runtime_error("M0 live shutdown failed");
    return 0;
}
