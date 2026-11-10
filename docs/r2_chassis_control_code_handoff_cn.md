# R2 夹爪视觉给底盘/状态机的控制码说明

## 1. 对接方式

视觉程序实时运行后，每一帧会向 stdout 输出一行 JSON。

底盘/状态机脚本不需要读取图片，也不需要调用 YOLO，只需要逐行读取视觉程序输出的 JSON。

## 2. 推荐启动命令

电脑端测试：

```powershell
cd E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision
.\tools\run_r2_gripper_v5.ps1 -Show:$false
```

Jetson 端上车：

```bash
cd /home/jetson/syf/vision_code
mkdir -p logs
CAMERA=0 DEVICE=cpu SHOW=0 JSON_OUT=logs/field_quick.jsonl ./tools/run_r2_gripper_v5_jetson.sh
```

## 3. JSON 示例

目标在左边：

```json
{"status":"tracking","dx_px":-72.2,"target_valid":1,"control_code":-1,"x_direction":-1,"confidence":0.86,"stable_frames":0}
```

目标在右边：

```json
{"status":"tracking","dx_px":85.4,"target_valid":1,"control_code":1,"x_direction":1,"confidence":0.88,"stable_frames":0}
```

目标进入阈值：

```json
{"status":"aligned","dx_px":12.3,"target_valid":1,"control_code":0,"x_direction":0,"confidence":0.90,"stable_frames":2}
```

视觉锁定：

```json
{"status":"locked","dx_px":7.8,"target_valid":1,"control_code":2,"x_direction":0,"confidence":0.91,"stable_frames":5}
```

目标丢失：

```json
{"status":"lost","dx_px":null,"target_valid":0,"control_code":-2,"x_direction":0,"confidence":0.0,"stable_frames":0}
```

真实输出会比上面多一些字段，例如 `timestamp_ms`、`dy_px`、`target_slot`，底盘第一版可以先忽略。

## 4. control_code 含义

底盘第一版建议优先读取 `control_code`：

```text
-2: 没有可靠目标，禁止抓取，停止当前微调或重新搜索
-1: 向左小步修正
 0: 左右已经进入阈值，保持或等待
 1: 向右小步修正
 2: 视觉已经 locked，停止微调，进入机械二次确认
```

## 5. 底盘脚本伪代码

```python
data = json.loads(line)
code = data["control_code"]

if code == -2:
    stop_motion()
    forbid_grab()
    search_or_reposition()
elif code == -1:
    nudge_left()
elif code == 0:
    hold_slow()
elif code == 1:
    nudge_right()
elif code == 2:
    stop_motion()
    verify_mechanics_then_grab()
```

## 6. 安全注意

`control_code == 2` 不代表马上夹取。

它只代表视觉左右方向已经稳定对准。真正闭合夹爪前，状态机还需要确认：

- 当前确实处于取端头流程。
- 夹爪已经打开。
- 底盘或机构已经停稳。
- 高度到位。
- 前后距离或机械限位到位。
- 停稳后继续读取 3 到 5 帧仍然是 `control_code == 2`。

以上都满足后，再允许夹爪闭合。

