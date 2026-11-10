# R2 夹爪视觉状态机接口说明

## 当前结论

R2 夹爪视觉模块已经可以通过 stdout 持续输出逐行 JSON。状态机可以把视觉程序作为独立进程启动，然后逐行读取 JSON，根据 `status` 和 `dx_px` 做左右微调。

当前已验证：

- 目标在画面左侧时，`dx_px < 0`。
- 目标在画面右侧时，`dx_px > 0`。
- 目标进入阈值并连续稳定后，`status == locked`。
- 目标丢失时，`status == search` 或 `status == lost`，状态机禁止抓取。

## 视觉程序运行命令

电脑端当前推荐命令：

```powershell
cd E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision
.\tools\run_r2_gripper_v5.ps1 -Show:$false -JsonOut logs\r2_gripper_json_only_test.jsonl
```

带调试画面的命令：

```powershell
cd E:\robocon26\robocon-2026-liangjiang-robotics\r2_gripper_vision
.\tools\run_r2_gripper_v5.ps1
```

## JSON 输出格式

视觉程序每帧输出一行 JSON，示例：

```json
{"status":"tracking","target_slot":1,"target_type":"rack_connector","dx_px":-42.1,"dy_px":-38.5,"confidence":0.86,"stable_frames":0,"timestamp_ms":123456,"target_valid":1,"control_code":-1,"x_direction":-1,"action_hint":"nudge_left","angle_deg":null,"detected_slots":1,"alignment_axes":"x","message":"single_target"}
```

状态机第一版建议只读取这些字段：

- `status`
- `control_code`
- `target_valid`
- `x_direction`
- `dx_px`
- `confidence`
- `stable_frames`

如果底盘同学希望只读一个整数，优先读取 `control_code`：

```text
control_code = -2: 没有可靠目标，禁止抓取，不要继续按旧方向动
control_code = -1: 向左小步修正
control_code =  0: 左右已经进入阈值，保持或等待
control_code =  1: 向右小步修正
control_code =  2: 视觉已锁定，停止微调，进入机械二次确认
```

`x_direction` 只表示左右方向：

```text
x_direction = -1: 向左小步修正
x_direction =  0: 不做左右修正
x_direction =  1: 向右小步修正
```

`search` / `lost` 时，`control_code = -2`，`target_valid = 0`。状态机应该优先使用 `control_code` 或 `target_valid` 区分“没目标”和“已经对中”。

## 状态含义

```text
search:
  当前没有找到可靠目标。禁止抓取。

tracking:
  找到目标，但左右偏差还没有进入阈值。状态机根据 dx_px 小步修正。

aligned:
  左右偏差已经进入阈值，但稳定帧数还不够。继续保持或低速微调。

locked:
  连续多帧稳定，允许状态机停止微调并执行抓取动作。

lost:
  曾经看到目标，但现在丢失。禁止抓取，回到搜索或重新预定位。
```

## 第一版动作建议

```python
if control_code == -2:
    no_grab()
    search_or_reposition()
elif control_code == 2:
    stop_motion()
    verify_mechanics_then_grab()
elif control_code == 1:
    nudge_right()
elif control_code == -1:
    nudge_left()
else:
    hold_slow()
```

当前约定：

- `dx_px > 0`：目标在夹爪基准点右侧，R2 或夹爪向右修正。
- `dx_px < 0`：目标在夹爪基准点左侧，R2 或夹爪向左修正。
- 第一版只闭环 `x` 方向，`dy_px` 先作为调试信息。

## 本次 JSON 测试结果

测试日志：

```text
logs\r2_gripper_json_only_test.jsonl
```

统计结果：

```text
总行数: 1492
坏 JSON: 0
search: 449
tracking: 443
aligned: 12
locked: 40
lost: 548
dx_px 最小值: -259.99
dx_px 最大值: 258.93
confidence 平均值: 0.89
stable_frames 最大值: 30
```

结论：stdout JSON 接口可用，状态机可以按逐行 JSON 读取方式进行联调。

注意：`locked` 只代表视觉已经对准，不代表夹爪可以无条件立刻闭合。真实上车时还需要确认底盘停稳、机械高度到位、前后距离到位、当前任务状态正确，再执行夹爪闭合。

## 上车后必须重新确认

- 摄像头固定到 R2 夹爪附近后，重新标定 `grab_center_x/y`。
- 确认 `dx_px` 正负方向和底盘实际移动方向一致。
- 先只让状态机低速左右微调，不执行真实抓取。
- 确认 `locked` 后目标确实对准夹爪机械中心，再允许夹爪动作。
- 如果实机视角下快接头经常被掌、拳、矛遮挡，需要补充实机失败样本或升级为端头检测加固定偏移估计。

