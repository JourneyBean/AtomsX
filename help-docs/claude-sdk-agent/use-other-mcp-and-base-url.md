可以，但要分两层看。

第一层，**自定义 MCP 服务器**：可以。Python 版 Claude Agent SDK 的 `ClaudeAgentOptions` 明确有 `mcp_servers` 配置项；官方参考还列出了可用的 MCP 传输类型，包括 `stdio`、`sse`、`http`，以及 SDK 内嵌的 in-process `sdk` server。官方示例也直接演示了 `create_sdk_mcp_server(...)` 后通过 `mcp_servers={"calc": calculator}` 接入。([Claude Platform][1])

第二层，**自定义 API 端点，不走 Anthropic 官方直连 API**：也可以，但“可以到什么程度”要分情况。SDK 官方参考说明 `ClaudeAgentOptions` 里有 `env`，可以把环境变量传给底层 Claude Code CLI；而 Claude Code 官方环境变量文档明确写了 `ANTHROPIC_BASE_URL` 可以用来覆盖 API endpoint，把请求转发到 proxy 或 gateway。官方还明确支持通过第三方平台提供 Claude，包括 Amazon Bedrock、Google Vertex AI、Microsoft Foundry，以及这些平台前面的 LLM gateway。([Claude Platform][1])

所以，如果你的意思是：

* **“我有自己的 MCP server，模型仍然是 Claude”**：可以，官方支持。([Claude Platform][1])
* **“我不用 api.anthropic.com，改走我自己的网关 / LiteLLM / 企业代理，但后面仍然是 Claude 或 Claude on Bedrock / Vertex / Foundry”**：可以，官方文档有明确路径，`ANTHROPIC_BASE_URL` / `ANTHROPIC_BEDROCK_BASE_URL` / `ANTHROPIC_VERTEX_BASE_URL` / `ANTHROPIC_FOUNDRY_BASE_URL` 都是文档化配置。官方甚至给了 LiteLLM 网关示例。([Claude][2])
* **“我想让 claude-agent-sdk 驱动完全非 Anthropic 模型，比如 OpenAI/Qwen/自研模型，只是伪装成一个 endpoint”**：这一点我没有找到官方正面支持文档。相反，仓库里有用户专门问“能否通过 LiteLLM 用非 Anthropic 模型”，该 issue 被关闭为 **not planned**；这更像是不被官方承诺支持的方向。也就是说，技术上可能有人会通过兼容层尝试，但从公开资料看，它不是官方支持矩阵的一部分。([GitHub][3])

一个最小示意大概是这样：

```python
from claude_agent_sdk import ClaudeAgentOptions, query

options = ClaudeAgentOptions(
    mcp_servers={
        "mytools": {
            "type": "http",
            "url": "http://127.0.0.1:8080/mcp",
            "headers": {"Authorization": "Bearer xxx"},
        }
    },
    env={
        "ANTHROPIC_BASE_URL": "http://your-gateway:4000",
        "ANTHROPIC_API_KEY": "your-key",
    },
)

# async for msg in query(prompt="...", options=options):
#     ...
```

这里 `mcp_servers` 是官方支持的，`env` 也是官方支持的；`ANTHROPIC_BASE_URL` 是否真正可用，取决于你的网关是否提供 Claude Code 期望的 Anthropic 兼容接口与相关行为。官方文档明确提到，改成非第一方 host 后，MCP tool search 的默认行为也会变化。([Claude Platform][1])

补一句实务判断：**如果你的目标是“自建 MCP + 自建网关，但后端仍跑 Claude”——这是可行路线；如果你的目标是“借 Claude Agent SDK 的 agent loop 去跑非 Claude 模型”——不要把它当成官方支持方案。** ([Claude][2])

如果你愿意，我可以直接给你一份“Python + 自定义 HTTP MCP + LiteLLM 网关”的可运行最小示例。

[1]: https://platform.claude.com/docs/en/agent-sdk/python "Agent SDK reference - Python - Claude API Docs"
[2]: https://code.claude.com/docs/en/llm-gateway "LLM gateway configuration - Claude Code Docs"
[3]: https://github.com/anthropics/claude-agent-sdk-python/issues/410 "Question: Is it possible to use Non-Anthropic models with Claude Agent SDK? · Issue #410 · anthropics/claude-agent-sdk-python · GitHub"
