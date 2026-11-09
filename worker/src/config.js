const num = (value, fallback) => {
  const n = Number(value);
  return Number.isFinite(n) && value !== "" && value !== undefined && value !== null ? n : fallback;
};
const str = (value, fallback = "") => (value === undefined || value === null ? fallback : String(value));
const flag = (value, fallback) => {
  if (value === undefined || value === null || value === "") return fallback;
  return ["1", "true", "yes", "on"].includes(String(value).toLowerCase());
};

export function settings(env) {
  const e = env || {};
  return {
    secretKey: str(e.SECRET_KEY, "change-me"),
    adminPassword: str(e.ADMIN_PASSWORD, "change-me"),
    tokenTtlHours: num(e.TOKEN_TTL_HOURS, 72),
    encryptionKey: str(e.ENCRYPTION_KEY),
    frontendBaseUrl: str(e.FRONTEND_BASE_URL),
    publicBaseUrl: str(e.PUBLIC_BASE_URL),
    cronSecret: str(e.CRON_SECRET),
    guardrailSecret: str(e.GUARDRAIL_SECRET),
    otariBaseUrl: str(e.OTARI_BASE_URL, "https://api.otari.ai/api/v1"),
    otariApiKey: str(e.OTARI_API_KEY),
    otariUserPrefix: str(e.OTARI_USER_PREFIX, "lder-elder-"),
    otariTimeoutSeconds: num(e.OTARI_TIMEOUT_SECONDS, 45),
    classifierModel: str(e.CLASSIFIER_MODEL, "lder-classifier"),
    classifierFallbackModels: str(e.CLASSIFIER_FALLBACK_MODELS),
    classifierReasoningEffort: str(e.CLASSIFIER_REASONING_EFFORT),
    summaryModel: str(e.SUMMARY_MODEL, "lder-summary"),
    summaryFallbackModels: str(e.SUMMARY_FALLBACK_MODELS),
    assistantModel: str(e.ASSISTANT_MODEL, "lder-assistant"),
    assistantFallbackModels: str(e.ASSISTANT_FALLBACK_MODELS),
    sttBaseUrl: str(e.STT_BASE_URL),
    sttApiKey: str(e.STT_API_KEY),
    sttModel: str(e.STT_MODEL, "whisper-large-v3"),
    sttLanguage: str(e.STT_LANGUAGE, "ml"),
    sttPrompt: str(e.STT_PROMPT),
    confidenceThreshold: num(e.CONFIDENCE_THRESHOLD, 0.55),
    mcpPublicUrl: str(e.MCP_PUBLIC_URL),
    mcpTokenTtlSeconds: num(e.MCP_TOKEN_TTL_SECONDS, 600),
    whatsappToken: str(e.WHATSAPP_TOKEN),
    whatsappPhoneNumberId: str(e.WHATSAPP_PHONE_NUMBER_ID),
    whatsappVerifyToken: str(e.WHATSAPP_VERIFY_TOKEN),
    whatsappAppSecret: str(e.WHATSAPP_APP_SECRET),
    whatsappApiVersion: str(e.WHATSAPP_API_VERSION, "v21.0"),
    whatsappTemplateName: str(e.WHATSAPP_TEMPLATE_NAME, "hello_world"),
    whatsappTemplateLanguage: str(e.WHATSAPP_TEMPLATE_LANGUAGE, "en_US"),
    emailApiUrl: str(e.EMAIL_API_URL),
    emailApiKey: str(e.EMAIL_API_KEY),
    emailFrom: str(e.EMAIL_FROM),
    retryDelays: str(e.RETRY_DELAYS_MINUTES, "15,30")
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean)
      .map(Number),
    finalWaitMinutes: num(e.FINAL_WAIT_MINUTES, 30),
    escalationDelayMinutes: num(e.ESCALATION_DELAY_MINUTES, 20),
    slotGraceMinutes: num(e.SLOT_GRACE_MINUTES, 60),
    summaryWeekday: num(e.SUMMARY_WEEKDAY, 6),
    summaryHourUtc: num(e.SUMMARY_HOUR_UTC, 12),
    enableScheduler: flag(e.ENABLE_SCHEDULER, true),
  };
}

export function modelChain(primary, fallbacks) {
  const chain = [];
  if (primary && primary.trim()) chain.push(primary.trim());
  for (const item of (fallbacks || "").split(",")) {
    const m = item.trim();
    if (m && !chain.includes(m)) chain.push(m);
  }
  return chain;
}
