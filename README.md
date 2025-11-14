# Langbot Plugin - GroupChattingContext

[LangBot](https://github.com/RockChinQ/LangBot) 注入群聊历史消息、额外 prompt 的插件。

此插件为 bot 参与 qq 群公聊设计。有助于增强开启 random 模式后的会话连贯性。

## 安装方法

配置完成 LangBot 主程序后使用管理员账号向机器人发送命令即可安装：

```
!plugin get https://github.com/sansui233/GroupChattingContext
```

## 功能

- bot 产生回复前的 20 条历史消息（数量可修改）注入到会话。
- 会标注所有说话者的 id （通常是 qq 号）。
- 每个群聊可单独设置 prompt，会追加到原 prompt 末尾，以方便 ai 识别不同群说话者关系。

注意：此插件会参与修改 langbot 维护的群聊会话消息。在启用此插件进行多轮对话后，发送 `!prompt` 命令会发现聊天记录格式有所变化。有可能影响其他基于 prompt 工作的插件效果。

## 配置

### 开启记录群聊历史消息

为防止 bot 成为海王（不是），同时记录过多群的信息，此插件使用群组白名单模式。

在 langbot 的 `pipeline.json` 中，配置群号和对应的 at 规则如下。

```json
"respond-rules": {
  "582256351": {
    "at": true
  }
}
```
### 插件配置（可选）

通常情况下不用配置此项。但……

如果要对特定群设置 prompt 和 limit，修改此插件目录下的 `config.json`

- prompt: 追加到 默认 prompt 后的内容
- limit: bot 产生回复前发送的历史记录条数
- self_name: 历史记录中自身的称呼（回复语句），为空则使用 bot 的 id

```json
{
  "991250350(替换为你的群号)":{
    "limit": 20,
    "propmt": "## Group Chatting Context\n 你现在正在一个三人小群里水群.",
    "self_name": "你"
  },
  "default":{
    "limit": 20,
    "propmt": "you are now in a group chatting.",
    "self_name": "你"
  }
}
```

## TODO

- [ ] throttled 在没有被 at 时判断是否需要根据上下文主动回复。

## 动机（填坑动力）

目前的 langbot 在群里中的体验有非常强的人机感，一是 bot 缺少主动性，每次都要呼唤“咒语”，如“hey siri”，在交互中，每多一个负反馈（无反馈）的步骤就是多一步的阻碍，如果开启每条消息必回复，则会变成社交恐怖分子。二是 langbot 缺乏群聊上下文，导致问答不连贯，带来了更多的工具感，random 模式下触发的回答也因此几乎没有意义。三是，LLM 补全只能一问一答或一问多答（发散+分段），无法在线上聊天时多问一答。LLM 的本身训练缺乏对于时序的模拟， 这是第一点缺乏主动性的一体两面，本质在于没有判断“当前情况是否应该回复”。此插件针对以上三点进行改进。