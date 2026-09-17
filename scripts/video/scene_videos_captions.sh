#!/usr/bin/env bash
# Burn per-segment Chinese captions into the five fly-through videos and concatenate
# them into one reel. Run AFTER render_scene_videos.py has produced *_flythrough_raw.mp4.
set -euo pipefail
cd "$(dirname "$0")/../.."
FONT=/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc
VDIR=runs/scene_v2/videos
[[ -f "$FONT" ]] || { echo "CJK font missing"; exit 2; }

cap () { # scene outfile "t1|t2:text1;t3|t4:text2;..."
  local scene=$1 out=$2 segs=$3
  local filters=() seg range text
  IFS=';' read -ra arr <<< "$segs"
  for seg in "${arr[@]}"; do
    range="${seg%%:*}"; text="${seg#*:}"
    filters+=("drawtext=fontfile=$FONT:text='$text':fontsize=34:fontcolor=white:borderw=3:bordercolor=black@0.85:x=(w-text_w)/2:y=h-90:enable='between(t,${range//|/,})'")
  done
  local joined; joined=$(IFS=,; echo "${filters[*]}")
  ffmpeg -y -v error -i "$VDIR/${scene}_flythrough_raw.mp4" -vf "$joined" \
    -c:v libx264 -crf 20 -preset medium -an "$VDIR/$out"
  echo "captioned: $VDIR/$out"
}

cap server_rack server_rack_flythrough.mp4 "\
0|2.9:数据机柜排障 · 全景;\
3|5.9:近层 · 备用节点 SPARE 待插入;\
6|8.6:当前 · 4 号槽位 SLOT4(precise 精插);\
8.7|10.5:中深 · 3 号节点 NODE3(被机架遮挡);\
10.6|12.3:证据视角 · NODE3 背面光纤接口;\
12.4|15:远层 · 柜顶告警灯 ALARM(persistent 监控)→ 全景"

cap drone_bench drone_bench_flythrough.mp4 "\
0|2.9:无人机检修台 · 全景;\
3|5.9:近层 · 电池仓 BAY 与电池 BAT(precise);\
6|8.9:护罩 GUARD(顺时针 30 度,角度参数);\
9|10.7:左后电机 M3 减震垫(被机臂遮挡);\
10.8|12.3:转场;\
12.4|15:远层 · 电压表 VOLTMETER(persistent 监控)→ 全景"

cap shelf_picking shelf_picking_flythrough.mp4 "\
0|2.9:仓储分拣站 · 全景;\
3|5.9:二层 · 红色包裹 RED(current);\
6|8.9:一层 · 蓝箱 BLUE(面单贴于背面);\
9|10.7:近层 · 拣选篮 BASKET(放置锚点);\
10.8|12.3:转场;\
12.4|15:远层 · 传送带端部与绿箱(双 background)→ 全景"

cap optical_bench optical_bench_flythrough.mp4 "\
0|2.9:光具座同轴校准 · 全景;\
3|5.7:近端 · 激光器;\
5.8|8.5:L1 待插入二号柱位 POST2(近层 precise);\
8.6|11.1:中景 · 折转反射镜 M(旋转+背面编号);\
11.2|12.9:远层 · 靶屏 TARGET 光斑(persistent);\
13|15:M 细节 → 全景"

cap dig_site dig_site_flythrough.mp4 "\
0|2.9:考古探方发掘 · 全景;\
3|5.7:坑内中层 · 3 号陶片 POT3(绳纹内壁);\
5.8|8.5:坑底 · 骨化石 BONE 与标记旗 FLAG;\
8.6|11.1:坑内俯瞰(深度即地层);\
11.2|13.3:坑外 · 全站仪 STAY(persistent 锁定);\
13.4|16:全景"

# engine_bay: standalone film (复刻 scene), deliberately NOT in the concat reel below.
# Windows follow the camera keyframe arrivals (final review P2: captions previously
# led the camera by 1.5-3s; camera reaches PLUGPORT at t=10.0, TENSIONER t=13, CONN t=14.5).
cap engine_bay engine_bay_flythrough.mp4 "\
0|2.9:任务驱动全息焦深提示 · 发动机舱维修（复刻）;\
3|8.9:近层：卡箍 CLAMP 逆时针 90°（precise）;\
9.6|12.4:中层：火花塞孔 PLUGPORT 插入对准（precise）;\
12.5|14.2:右端：皮带张紧轮 TENSIONER;\
14.3|15.4:远层：连接器 CONN 背面检查（persistent）;\
15.5|16:调焦跨度 0.83m · N=6000 确定性分配"

printf "file '%s/%s'\n" "$VDIR" server_rack_flythrough.mp4 \
  "$VDIR" drone_bench_flythrough.mp4 \
  "$VDIR" shelf_picking_flythrough.mp4 \
  "$VDIR" optical_bench_flythrough.mp4 \
  "$VDIR" dig_site_flythrough.mp4 > /tmp/v2_video_list.txt
ffmpeg -y -v error -f concat -safe 0 -i /tmp/v2_video_list.txt \
  -c copy "$VDIR/holocue_v2_scenes.mp4"
echo "reel: $VDIR/holocue_v2_scenes.mp4"
ls -la "$VDIR"
