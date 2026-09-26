#!/bin/sh
# lbc-verify-headless.sh - run on the board after flashing.
#
#   ssh root@192.168.77.2 'sh -s' < tools/lbc-verify-headless.sh
#
# Round 1: display/audio/Bluetooth trimmed.
# Round 2: USB gadget/adb, CAN, SCSI/ATA/NVMe/MD, GPU(Mali), HID, unused
#          filesystems and debug options trimmed; WiFi narrowed to RTL8822CE.
# Kept: MIPI CSI/ISP/VPSS/RGA, NPU, RTL8822CE WiFi, LEDs (sys_led), AMP/M0.

pass=0; fail=0; note=0
ok()   { pass=$((pass+1)); printf '  [ OK ] %s\n' "$*"; }
bad()  { fail=$((fail+1)); printf '  [FAIL] %s\n' "$*"; }
info() { note=$((note+1)); printf '  [note] %s\n' "$*"; }

cfg() { zcat /proc/config.gz 2>/dev/null; }
# off = "# X is not set" OR the symbol is gone entirely (parent disabled).
cfg_off() { cfg | grep -qE "^$1=[ym]$" && bad "$1 still set" || ok "$1 off"; }
cfg_on()  { cfg | grep -qE "^$1=[ym]$" && ok "$1 set"         || bad "$1 not set"; }

printf '==== model / kernel ====\n'
printf '  model : %s\n' "$(tr -d '\0' < /proc/device-tree/model 2>/dev/null)"
printf '  kernel: %s\n' "$(uname -r)"

printf '\n==== kernel trims (want: off) ====\n'
for c in CONFIG_BT CONFIG_BT_HCIBTUSB CONFIG_SOUND CONFIG_SND CONFIG_DRM_ROCKCHIP \
	 CONFIG_ROCKCHIP_DW_HDMI CONFIG_ROCKCHIP_DW_DP CONFIG_ROCKCHIP_DW_MIPI_DSI \
	 CONFIG_FB CONFIG_FRAMEBUFFER_CONSOLE CONFIG_BACKLIGHT_CLASS_DEVICE CONFIG_RK_HEADSET \
	 CONFIG_USB_GADGET CONFIG_CAN CONFIG_SCSI CONFIG_ATA CONFIG_BLK_DEV_NVME \
	 CONFIG_MD CONFIG_BLK_DEV_DM CONFIG_MALI_BIFROST CONFIG_MALI_MIDGARD \
	 CONFIG_R8168 CONFIG_R8169 CONFIG_HID CONFIG_USB_HID CONFIG_USB_STORAGE \
	 CONFIG_USB_SERIAL CONFIG_XFS_FS CONFIG_BTRFS_FS CONFIG_CIFS CONFIG_NFS_FS \
	 CONFIG_PM_DEBUG CONFIG_SCHEDSTATS CONFIG_DEBUG_INFO CONFIG_PRINTK_TIME \
	 CONFIG_DYNAMIC_DEBUG; do
	cfg_off "$c"
done

printf '\n==== kept on purpose (want: set) ====\n'
for c in CONFIG_DRM CONFIG_ROCKCHIP_RKNPU CONFIG_ROCKCHIP_RKNPU_DRM_GEM \
	 CONFIG_VIDEO_ROCKCHIP_CIF CONFIG_VIDEO_ROCKCHIP_ISP CONFIG_VIDEO_ROCKCHIP_VPSS \
	 CONFIG_VIDEO_ROCKCHIP_RGA CONFIG_ROCKCHIP_MPP_SERVICE CONFIG_ROCKCHIP_AMP \
	 CONFIG_RPMSG_ROCKCHIP_MBOX CONFIG_RPMSG_VIRTIO CONFIG_RTW88_8822CE \
	 CONFIG_RTW88_CORE CONFIG_RTW88_PCI CONFIG_CFG80211 CONFIG_MAC80211 CONFIG_RFKILL_RK \
	 CONFIG_STMMAC_ETH CONFIG_USB_XHCI_HCD CONFIG_USB_DWC3 \
	 CONFIG_LEDS_CLASS CONFIG_LEDS_GPIO CONFIG_LEDS_TRIGGER_HEARTBEAT \
	 CONFIG_INPUT_EVDEV CONFIG_EXT4_FS CONFIG_VFAT_FS CONFIG_SENSORS_PWM_FAN; do
	cfg_on "$c"
done

printf '\n==== devices/services that must be gone ====\n'
if ls /sys/class/drm/ 2>/dev/null | grep -qE 'card[0-9]+-'; then
	bad "DRM display connector present"
else
	ok "no DRM display connector"
fi
[ -d /dev/dri ] && info "/dev/dri exists (expected: rknpu DRM node)"
[ -d /proc/asound ] && bad "/proc/asound exists" || ok "no /proc/asound"
command -v bluetoothd >/dev/null 2>&1 && bad "bluetoothd present" || ok "no bluetoothd"
for s in S49weston S50pulseaudio S40bluetoothd S99chromium-wayland.sh S50usbdevice.sh; do
	[ -e "/etc/init.d/$s" ] && bad "$s present" || ok "$s absent"
done
ls /usr/lib/chromium >/dev/null 2>&1 && bad "/usr/lib/chromium present" || ok "no chromium libs"
ls /usr/lib/libmali* >/dev/null 2>&1 && bad "libmali present" || ok "no libmali"
command -v adbd >/dev/null 2>&1 && bad "adbd present" || ok "no adbd"
[ -z "$(ls /sys/class/udc 2>/dev/null)" ] && ok "no USB gadget UDC" || bad "UDC present: $(ls /sys/class/udc)"
ls /dev/sd* >/dev/null 2>&1 && bad "/dev/sd* present" || ok "no SCSI disk nodes"
ls /dev/mali0 >/dev/null 2>&1 && bad "/dev/mali0 present" || ok "no /dev/mali0"

printf '\n==== kept subsystems ====\n'
ip -br addr show eth0 2>/dev/null | grep -q 192.168.77.2 && ok "eth0 = 192.168.77.2/24" || bad "eth0 not static"
for n in mcu@60000000 amp-shmem@47900000 rpmsg@47d00000 rpmsg-dma@47f00000; do
	[ -e "/proc/device-tree/reserved-memory/$n" ] && ok "reserved-memory: $n" || bad "missing $n"
done
[ -e /sys/bus/platform/drivers/rockchip-amp ] && ok "rockchip-amp driver present" || bad "rockchip-amp missing"
if command -v lspci >/dev/null 2>&1; then
	lspci -nnk 2>/dev/null | grep -q 'rtw_8822ce' && ok "RTL8822CE bound to rtw_8822ce" || bad "RTL8822CE not bound"
fi
[ -e /sys/class/leds/sys_led ] && ok "sys_led present" || bad "sys_led missing"
ls /dev/rknpu* >/dev/null 2>&1 && ok "/dev/rknpu* present (NPU)" || info "no /dev/rknpu*"
ls /dev/video* >/dev/null 2>&1 && ok "video nodes present (camera)" || info "no /dev/video*"
for m in b43 iwlwifi mt76 rtw88_8822b rtl_bt; do
	find /lib/modules -name "$m*.ko*" 2>/dev/null | grep -q . && bad "$m module present" || ok "no $m module"
done
command -v cyclictest >/dev/null 2>&1 && ok "cyclictest available (rt-tests)" || bad "cyclictest missing"

printf '\n==== firmware / size ====\n'
printf '  /lib/firmware: %s\n' "$(du -sh /lib/firmware 2>/dev/null | awk '{print $1}')"
printf '  /lib/modules : %s\n' "$(du -sh /lib/modules 2>/dev/null | awk '{print $1}')"

printf '\n==== quick load / thermal ====\n'
printf '  uptime : %s\n' "$(cut -d. -f1 /proc/uptime)s"
printf '  mem    : %s\n' "$(free -h 2>/dev/null | awk '/Mem:/{print $3" used / "$2" total"}')"
for z in /sys/class/thermal/thermal_zone*/temp; do
	[ -r "$z" ] && printf '  %s: %s\n' "$(basename "$(dirname "$z")")" "$(cat "$z" 2>/dev/null)"
done

printf '\n==== rpmsg ====\n'
dmesg 2>/dev/null | grep -iE 'rockchip-rpmsg|virtio_rpmsg_bus|rpmsg host is online' | sed 's/^/  /' || true

printf '\n==== summary ====\n'
printf '  pass=%d fail=%d note=%d\n' "$pass" "$fail" "$note"
[ "$fail" -eq 0 ]
