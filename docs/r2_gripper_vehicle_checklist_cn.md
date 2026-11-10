# R2 夹爪视觉上车联调清单

本文用于 R2 夹爪视觉从电脑测试转到 Jetson / 机器人联调。当前视觉任务是输出夹爪相对目标快接头的左右偏差 `dx_px`，状态机根据该偏差做小步修正。

## 0. 当前阶段结论

- v5 模型在单槽位安装端头测试中识别稳定。
- `dx_px` 方向已验证：目标在左侧为负，目标在右侧为正。
- `locked` 状态已验证，可以稳定触发。
- stdout JSON 状态机 demo 已验证：
  - `NUDGE_LEFT`
  - `NUDGE_RIGHT`
  - `STOP_AND_GRAB`
  - `NO_GRAB`
- 当前摄像头未固定在 R2 夹爪，`grab_center_x/y` 仍是临时值。
- 当前测试环境不是比赛环境，后续仍需真实夹爪视角、灰色端头、真实端头架和 Jetson 联调。

## 1. 当前推荐模型

电脑测试当前推荐模型：

```text
models\rack_connector_v5_single_slot_best.pt
```

上车前建议复制到 Jetson 或仓库模型目录，并改成稳定路径，例如：

```text
r2_gripper_vision/models/rack_connector_v5_single_slot_best.pt
```

## 2. 当前推荐参数

当前桌面测试推荐：

```text
conf = 0.40
iou = 0.25
alignment_axes = x
align_threshold_px = 25
lock_frames = 5
```

注意：这些不是最终比赛参数。摄像头装到 R2 夹爪后，需要重新验证。

## 3. Jetson 需要准备

Jetson 需要：

- USB 摄像头可被系统识别。
- Python 环境可运行 OpenCV 和 Ultralytics / YOLOv8。
- 能访问模型文件 `best.pt`。
- 能运行视觉程序并输出 stdout JSON。

最小依赖：

```bash
pip install ultralytics opencv-python numpy pyyaml
```

如果后续为了速度优化，可以再做 TensorRT 导出，但第一版先跑通 `.pt`。

## 4. 摄像头安装要求

摄像头建议固定在：

- R2 夹爪附近或夹爪上方。
- 朝向端头架目标区域。
- 略俯视目标。
- 最终夹取时目标尽量在画面中心区域，不要靠广角边缘。

安装后不要轻易移动摄像头。只要摄像头位置变了，`grab_center_x/y` 就必须重新标定。

## 5. 上车后标定夹爪中心

摄像头固定后，运行：

```powershell
cd E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision
$env:PYTHONPATH = "E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision"
.\.venv\Scripts\python.exe tools\pick_grab_center.py --camera 1
```

在画面里点击真实夹爪抓取中心。把输出写入：

```text
configs\r2_gripper.yaml
```

需要修改：

```yaml
grab_center_x: xxx
grab_center_y: yyy
```

标定后重新测试：目标实际被夹爪对准时，`dx_px` 应接近 0。

## 6. 视觉实时运行命令

电脑测试命令：

```powershell
cd E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision
$env:PYTHONPATH = "E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision"
$env:YOLO_CONFIG_DIR = "E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision\Ultralytics"
$env:MPLCONFIGDIR = "E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision\matplotlib_cache"

.\.venv\Scripts\python.exe -m head_rack_align.app `
  --model models\rack_connector_v5_single_slot_best.pt `
  --config configs\r2_gripper.yaml `
  --camera 1 `
  --device cpu `
  --conf 0.40 `
  --iou 0.25 `
  --draw-detections `
  --show
```

Jetson 上把路径和 `device` 改成 Jetson 实际环境。

## 7. 状态机读取字段

视觉程序每帧输出一行 JSON，核心字段：

```json
{
  "status": "tracking",
  "dx_px": -36.8,
  "confidence": 0.84,
  "stable_frames": 0
}
```

状态含义：

- `tracking`：看到目标，但还没对准。
- `aligned`：偏差进入阈值，但稳定帧数还不够。
- `locked`：连续稳定，可以抓取。
- `search`：当前没找到可靠目标。
- `lost`：曾经看到目标，但现在丢失。

动作建议：

```text
status == locked:
  停止微调，进入抓取

status == tracking or aligned:
  dx_px < 0，向左小步修正
  dx_px > 0，向右小步修正

status == search or lost:
  禁止抓取，重新搜索或回预定位
```

第一版只闭环 `dx_px`，高度和前后距离先交给机械限位、预定位或固定动作。

## 8. 状态机 demo 命令

```powershell
cd E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision
$env:PYTHONPATH = "E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision"
$env:YOLO_CONFIG_DIR = "E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision\Ultralytics"
$env:MPLCONFIGDIR = "E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision\matplotlib_cache"

.\.venv\Scripts\python.exe tools\state_machine_reader_demo.py `
  --model models\rack_connector_v5_single_slot_best.pt `
  --config configs\r2_gripper.yaml `
  --camera 1 `
  --conf 0.40 `
  --show
```

期望输出：

```text
NUDGE_LEFT
NUDGE_RIGHT
STOP_AND_GRAB
NO_GRAB search_or_reposition
```

## 9. 上车联调顺序

1. 摄像头固定到夹爪附近。
2. 确认 Jetson 能打开摄像头。
3. 运行视觉程序确认能看到快接头。
4. 标定 `grab_center_x/y`。
5. 只测试静止目标，确认 `dx_px` 正负方向。
6. 状态机只做低速左右微调，不抓取。
7. 验证 `dx_px` 能被修到阈值内。
8. 验证 `locked` 能稳定出现。
9. 空夹爪动作测试，不夹端头。
10. 低速实夹测试。
11. 记录失败样本，补数据再训练。

## 10. 失败排查

如果经常 `lost`：

- 降低 `conf`，例如从 `0.40` 改为 `0.35`。
- 检查快接头是否被完全遮挡。
- 补充该视角数据。

如果误框背景：

- 提高 `conf`。
- 补负样本。
- 限制中心 ROI。

如果 `dx_px` 方向反了：

- 状态机修正方向需要反向。
- 先不要抓取。

如果 `locked` 但夹不准：

- 重新标定 `grab_center_x/y`。
- 缩小 `align_threshold_px`。
- 检查夹爪机械抓取中心和画面中心是否一致。

如果画面边缘识别不稳：

- 让预定位把目标带到画面中心。
- 后续做畸变标定或使用中心 ROI。

## 11. 后续数据补充

优先补：

- 真实夹爪安装视角。
- 灰色比赛端头。
- 真实端头架。
- 快接头部分可见和完全不可见两类样本。
- 运动模糊、强光、暗光、反光。
- `lost` 和误框时的截图。

如果实机视角下快接头经常完全不可见，需要升级备用方案：

```text
检测端头本体 -> 根据固定几何偏移估计快接头/抓取中心
```

当前第一版仍以快接头可见时的夹爪左右修正为主。

