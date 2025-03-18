# Langbot Plugin - GroupChattingContext

[LangBot](https://github.com/RockChinQ/LangBot) 注入群聊上下文信息的插件。为qq群公聊设计。

## 安装方法

配置完成 LangBot 主程序后使用管理员账号向机器人发送命令即可安装：

```
!plugin get https://github.com/sansui233/GroupChattingContext
```

## 功能

bot 产生回复前的 20 条历史消息注入到会话。会注入所有说话者的身份识别信息（qq号）。

## 配置

为防止 bot 成为海王（不是），同时记录过多个群的信息，此插件使用群组白名单模式。

因为需要在 langbot 的 `pipeline.json` 中，配置群号和对应的 at 规则。
```json
"respond-rules": {
  "582256351": {
    "at": true
  }
}
```
