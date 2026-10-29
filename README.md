# sound

一个用于视频音效选材的 Claude Code Skill。从 [Freesound](https://freesound.org) 搜索和下载真实音效，结合下载量、评分人数、上传者描述、时长与许可证，帮助 Agent 为画面挑选合适的声音。

适用于转场、卡片入场、按钮点击、纸张滑动、碰撞等视频音效需求。Skill 的工作范围是音效搜索、筛选与下载；时长和能量分析可配合 FFmpeg 完成。

## 安装

需要 Claude Code、Python 3，以及可访问 Freesound 的网络。搜索和下载脚本仅使用 Python 标准库，无需安装 Python 第三方依赖。

在项目根目录执行：

```bash
git clone https://github.com/vibe-motion/sound.git .claude/skills/sound
```

核心文件：

```text
.claude/skills/sound/
├── SKILL.md                    # Agent 的技能入口与选材规则
├── scripts/
│   ├── sfx.py                  # Freesound 搜索与下载
│   └── clash_freesound.py      # 特定 ClashX Meta 环境的网络辅助脚本
└── references/
    └── local-setup.md           # 作者的本地网络配置参考
```

## 在 Claude Code 中使用

安装后，在视频项目中直接描述音效需求，例如：

> 用 sound 帮我找一个卡片飞入时的短 whoosh，约 0.3 秒，适合轻快的产品演示，只选 CC0，下载到 sfx/。

> 给开关切换找一个柔和、不刺耳的点击音效。先给出候选、下载量、评分人数和试听链接。

Skill 引导 Agent：

1. 将画面动作转成英文关键词，在 Freesound 搜索候选。
2. 先判断声音来源、描述和时长是否符合画面，再参考下载量与评分人数，说明推荐依据。
3. 按使用需求筛选许可证；需要人工试听时提供预览链接。
4. 下载选中的音效，必要时用 FFmpeg 检查时长与能量分布，并保留所需署名信息。

下载量与评分只是选材线索，不代表声音一定适合当前画面；Agent 也不应把这些信号当作已经试听过的结论。

## 直接运行脚本

脚本也可独立使用。以下命令均在项目根目录执行：

```bash
S=.claude/skills/sound/scripts/sfx.py

# 搜索 CC0 音效，并显示试听链接
python3 "$S" freesound "soft whoosh" --license cc0 --urls

# 搜索纸张滑动，允许 CC0 和需要署名的 Attribution 音效
python3 "$S" freesound "paper slide" --license by -n 5

# 下载：把占位符替换为本次搜索返回的 fs:ID，可一次传入多个
python3 "$S" get sfx/ "fs:<id1>" "fs:<id2>"
```

搜索结果会缓存在 `~/.cache/sfx-sources/index.json`。下载命令依赖这份缓存，因此需要先搜索，再使用结果中的 `fs:ID` 下载。当前下载的是 Freesound 的 MP3 预览文件，不是上传者的原始音频。

常用搜索参数：

| 参数 | 作用 |
| --- | --- |
| `--license cc0` | 仅搜索 CC0 |
| `--license by` | 搜索 CC0 和 Attribution |
| `--license any` | 不过滤许可证，默认值 |
| `--urls` | 显示试听链接 |
| `-n 5` | 最多显示 5 条结果，默认 8 条 |
| `--sort relevance` | 获取相关结果后按下载量重新排序，默认方式 |
| `--sort downloads` / `rating` / `short` | 分别按下载量、评分或时长排序 |
| `--pages 3` | 从起始页抓取的页数，默认 3 页 |
| `-p 2` | 从第 2 页开始搜索，默认第 1 页 |

## 许可证与署名

每条音效的许可证可能不同。脚本支持按 CC0 或 Attribution 筛选；默认 `any` 也可能返回 BY-NC 等其他许可的音效，使用前应检查对应条目的许可要求。

对于非 CC0 音效，`get` 会输出作者署名提示。这只是作者信息提示，交付时还应保留音效来源与许可证信息，按对应条目的要求补全署名。

## 网络排查

搜索与下载使用当前终端的 HTTP/HTTPS 代理设置。遇到超时，可先检查 Freesound 是否可访问，以及终端代理是否生效。批量下载可在同一个 `get` 命令中传入多个 ID，脚本会并发处理。

[`references/local-setup.md`](references/local-setup.md) 和 [`scripts/clash_freesound.py`](scripts/clash_freesound.py) 针对作者的 macOS / ClashX Meta 配置。辅助脚本的 `--fix` 会修改本机 Clash 配置并切换节点，仅在环境匹配且需要调整代理时使用。
