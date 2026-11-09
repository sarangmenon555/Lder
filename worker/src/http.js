export class HttpError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

export function json(data, status = 200, headers = {}) {
  if (status === 204) return new Response(null, { status, headers });
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json", ...headers } });
}

export async function readJson(request) {
  try {
    const body = await request.json();
    if (body === null || typeof body !== "object") throw new Error("bad");
    return body;
  } catch {
    throw new HttpError(422, "Request body must be valid JSON");
  }
}
