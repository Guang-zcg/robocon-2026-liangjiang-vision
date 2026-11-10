# R2 夹爪视觉安全逻辑

## 核心原则

视觉模块的 `locked` 不等于立刻夹取。

`locked` 只表示：

```text
目标在画面中
目标置信度足够
目标相对夹爪基准点的 x 偏差进入阈值
并且连续稳定了若干帧
```

真正闭合夹爪前，还必须由 R2 状态机确认机械条件。

## 夹爪什么时候打开

夹爪打开不应该由视觉模块控制。

建议流程：

```text
R2 离开准备区或进入取端头任务前:
  夹爪保持打开

R2 接近端头架前:
  确认夹爪打开
  确认高度/前后距离进入预定位

进入视觉对准:
  夹爪仍然保持打开
  只允许底盘或机构做低速左右微调
```

视觉模块只输出 `dx_px` 和 `status`，不直接发夹爪开合命令。

## 什么时候允许闭合夹爪

建议状态机不要看到 `locked` 就立刻夹，而是走两段确认：

```text
1. tracking/aligned:
   根据 dx_px 左右微调。

2. locked:
   先停止底盘或机构微调。

3. stop_verify:
   机器人完全停稳后，再连续读取 3 到 5 帧。
   如果仍然 locked，才进入 close_gripper。

4. close_gripper:
   执行夹爪闭合。

5. post_check:
   用夹爪电流、限位、编码器、行程或简单延时确认是否夹到。
```

更安全的伪代码：

```python
if status in ("search", "lost") or dx_px is None:
    forbid_grab()
    search_or_reposition()

elif status in ("tracking", "aligned"):
    keep_gripper_open()
    nudge_left_or_right(dx_px)

elif status == "locked":
    stop_motion()
    if chassis_is_still() and height_ready() and distance_ready() and locked_after_stop():
        close_gripper()
    else:
        keep_gripper_open()
```

## 如果误判 locked 但没有真正到位

这件事必须用“多条件门控”防住，不能只靠 YOLO。

建议状态机设置这些门：

- `vision_locked == true`
- `abs(dx_px) < threshold`
- `confidence > threshold`
- `stable_frames >= lock_frames`
- 底盘速度接近 0
- 机械高度到位
- 前后距离或机械限位到位
- 当前处于“端头架取端头”状态，不在其他状态
- 目标槽位编号和任务要求一致

只有这些都满足，才允许夹爪闭合。

## 如果到时候不能识别怎么办

不能识别时，视觉会输出：

```text
search 或 lost
dx_px = null
```

状态机动作建议：

```text
search:
  不抓取。
  小范围低速左右搜索，或者回到预定位点重新对准。

lost:
  不抓取。
  停止当前微调，后退或回预定位，再重新进入 search。

timeout:
  如果超过规定时间仍不能识别，放弃本次抓取或切换到保守机械方案。
```

不能识别时绝对不要凭上一次 `dx_px` 继续夹。

## 赛场级后续优化

当前模型主要识别 `rack_connector`。如果实机夹爪视角下快接头被掌、拳、矛遮挡，需要升级备用方案：

```text
检测端头本体或槽位结构
根据固定几何偏移估计快接头/抓取中心
再输出 dx_px
```

也就是说：

```text
快接头可见:
  直接识别 rack_connector

快接头经常不可见:
  识别 spear/fist/palm 或槽位特征
  用固定偏移推算抓取中心
```

第一版先使用快接头可见方案，因为它最直接，也已经通过了电脑端状态机接口测试。

