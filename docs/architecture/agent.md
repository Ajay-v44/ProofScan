# Inspection agent

The purchase flow compares advertised memory and largest-drive capacity with Windows or simulator readings. The buyer can also enter a minimum battery health. Missing readings become unavailable findings.

LangGraph validates scan inputs, compares claims and plans up to three evidence requests. The workflow persists its findings and requests beside the scan. Exterior-photo prompts name a missing angle. The published report records missing evidence so that a buyer can see the gaps. Automatic retesting across native clients remains pending.

The optional Moonshot adapter suggests structured listing claims when a signed-in buyer requests it. Buyers review the results and submit their own claims. The API caps output tokens and calls per account, and records token usage when provided. It sends the entered listing text and keeps hardware and photo data local. Moonshot credentials come from the developer console and are configured in the ignored environment file. Provider timeouts and invalid responses leave manual claim entry available.

Set `KIMI_API_KEY`, `KIMI_BASE_URL` and a Moonshot model ID that supports JSON responses in `KIMI_MODEL`. `KIMI_VISION_MODEL` is reserved for visual reasoning; the current image checks run locally with OpenCV.
