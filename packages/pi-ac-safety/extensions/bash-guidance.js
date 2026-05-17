const GUIDANCE_MARKER = "## ac-safety Bash guidance";

function hasBashTool(systemPromptOptions) {
  const selectedTools = systemPromptOptions?.selectedTools;
  return Array.isArray(selectedTools) && selectedTools.some((tool) => String(tool).toLowerCase() === "bash");
}

export default function registerAcSafetyBashGuidance(pi) {
  pi.on("before_agent_start", async (event) => {
    if (!hasBashTool(event.systemPromptOptions) || event.systemPrompt.includes(GUIDANCE_MARKER)) {
      return;
    }

    return {
      systemPrompt: `${event.systemPrompt}

${GUIDANCE_MARKER}

Do not route shell output to \`/dev/null\`; ac-safety blocks it. Prefer plain output, command-specific quiet flags such as \`grep -q\`, \`rg -q\`, or \`git diff --quiet\`, file tests such as \`test -e\`, and bounded output such as \`head\`.
`,
    };
  });
}
