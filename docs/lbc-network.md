# LBC3 直连以太网排查

项目镜像为板端 `eth0` 配置 `192.168.77.2/24`，宿主机对应网口
`enp195s0` 应使用 `192.168.77.1/24`。接口状态为 `UP`、有地址或网口灯
闪烁，都不能单独证明端到端通信正常。

从 zenith 根目录配置直连：

```bash
sudo tools/lbc-host-link.sh up
ip route get 192.168.77.2
ping -c 3 192.168.77.2
ssh root@192.168.77.2
```

脚本让 NetworkManager 不管理该网口，启用接口、配置地址及直连路由，并
添加优先级 100 的 `to 192.168.77.0/24 lookup main` 策略规则。
该规则使直连流量优先进入 main 表，绕过 Mihomo/Tailscale 等更低优先级
的策略。重复运行不会重复添加同一规则。

`ip route get` 应显示 `dev enp195s0 src 192.168.77.1`，不能指向
`Mihomo` 或 `table 2022`。使用其他网卡或地址时，脚本支持
`up <iface> <host-ip> <prefix>`，板端地址可通过 `BOARD_IP` 覆盖。
脚本需要 Python 3 计算 IPv4 网段。恢复 NetworkManager 管理用
`sudo tools/lbc-host-link.sh down`；它也删除对应的优先级 100 策略规则。

## 分层检查

宿主机：

```bash
ip -br addr show enp195s0
ip -d link show enp195s0
ethtool enp195s0
ip -s link show enp195s0
ip neigh show dev enp195s0
ip route get 192.168.77.2
ip rule show
```

`<UP>` 表示接口已启用；`LOWER_UP` 和 `carrier=1` 才表示物理链路建立。
`state DOWN` 还要结合 flags 判断，不能直接当作接口没有启用。检查
`Link detected`、速度、carrier 是否反复变化，再检查地址、路由、ARP 和
收发包计数。灯的闪烁方式不能替代这些检查。

板端可通过调试串口执行：

```bash
ip -br addr
ip route
cat /sys/class/net/eth0/carrier
cat /sys/class/net/eth0/operstate
cat /sys/class/net/eth0/speed
cat /sys/class/net/eth0/duplex
ip -s link show eth0
dmesg | tail -40
```

串口参数为 **1500000、8N1、无流控**。USB 串口重新枚举后可能从
`/dev/ttyACM0` 变成 `ttyACM1`，建议优先使用
`/dev/serial/by-id/` 中对应设备的稳定路径。串口重新枚举本身不能证明
板子重启，需结合板端 `uptime` 和启动日志判断。

## 2026-09-30 现场记录

- 宿主机配置了 `192.168.1.2/24`，而板端仍是 `192.168.77.2/24`，网段不匹配。
- 启用宿主机网口后，两端都报告千兆全双工；板端日志为
  `Link is Up - 1Gbps/Full`。约 20 秒连续观察没有发现 carrier 变化。
- 原宿主机优先级 100 规则只覆盖 `192.168.1.0/24`。访问板端
  `192.168.77.2` 被送往 `Mihomo table 2022`，需要补充实际直连网段的规则。
- 串口曾从 `ttyACM0` 重新枚举为 `ttyACM1`；之后可继续读到板端 root shell。

以上说明当时物理链路已建立，不能据此认定网线完全没有间歇性故障。
修正宿主机配置后的 ping/SSH 结果需继续核实。
