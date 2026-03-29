支持。

官方 Python Agent SDK 的 `ClaudeAgentOptions` 里就有 `model` 和 `fallback_model` 字段，其中 `model` 的说明是“Claude model to use”，`fallback_model` 是主模型失败时的回退模型。也就是说，在 SDK 层可以直接指定模型。([Claude API Docs][1])

最直接的写法就是：

```python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    model="claude-opus-4-6",
    fallback_model="claude-sonnet-4-6",
)

async for msg in query("Review this repo", options=options):
    print(msg)
```

文档里还给了迁移示例，明确出现了 `ClaudeAgentOptions(model="claude-opus-4-6", ...)`，这也侧面证明 Python SDK 官方支持在 options 中改模型。([Claude Platform][2])

关于“能填什么值”，Claude Code 的模型配置文档写得比较清楚：可以用别名，也可以用完整模型名。别名包括 `default`、`sonnet`、`opus`、`haiku`、`sonnet[1m]`、`opus[1m]`、`opusplan`；如果要固定版本，可以用完整 ID，比如 `claude-opus-4-6`。([Claude][3])

同一套文档还说明了模型可通过多种方式设置，优先级从高到低大致是：
会话内 `/model <alias|name>`，
启动参数 `claude --model <alias|name>`，
环境变量 `ANTHROPIC_MODEL=<alias|name>`，
以及 settings 里的 `model` 字段。([Claude][3])

如果你还会用到 subagent，官方也支持给 subagent 单独指定模型。文档写明 subagent 的 `model` 可以是别名、完整模型 ID，或者 `inherit` 继承主会话模型。([Claude][4])

不过有一个边界要注意：官方文档表述始终是 **Claude model**，并列出的也是 Claude 系列模型与别名；我没有在官方文档里看到“任意非 Claude 模型名都受支持”的说法。换句话说，**支持改模型，但官方文档支持范围是 Claude 系列及其 provider 映射，不是通用任意模型路由。** settings 文档里的 `modelOverrides` 也是把 **Anthropic model IDs** 映射到 provider-specific IDs。([Claude API Docs][1])

你如果想要，我可以下一步直接帮你整理一份：

1. Python SDK 里如何切换 `sonnet / opus / haiku`，
2. 如何配 `ANTHROPIC_MODEL`，
3. 如何在 Bedrock / Vertex / 自建 gateway 下做 `modelOverrides`。

[1]: https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-python "Agent SDK reference - Python - Claude API Docs"
[2]: https://platform.claude.com/docs/en/agent-sdk/migration-guide "Migrate to Claude Agent SDK - Claude API Docs"
[3]: https://code.claude.com/docs/en/model-config "Model configuration - Claude Code Docs"
[4]: https://code.claude.com/docs/en/sub-agents "Create custom subagents - Claude Code Docs"
