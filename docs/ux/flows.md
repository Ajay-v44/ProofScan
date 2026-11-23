# UX and demo

## Demo script

1. From the buyer workspace, create a verification for a laptop advertised with 16 GiB memory, a 1,000 GB drive and at least 85% battery health.
2. Open the private link in a different browser context. Show the consent screen and how it controls collection.
3. For a real device, download a ticket and use the Windows collector on the device being sold. Import the scan on the seller page. For the matching simulator, enable the simulator and select its matching fixture.
4. Review the captured readings and claim comparisons. Share the report, return to the buyer workspace, refresh, and open the report.
5. Show the public signature check. Then demonstrate the mismatched fixture and decline sharing from a separate request.

## Handoff demo

1. Open Handoffs and create a simulator handoff. Start and record the baseline.
2. Optionally create the private acceptance link, open it in a separate browser session and accept. Refresh the owner page and mark the asset as handed off.
3. Start the return check and record the return. The simulated comparison shows Samsung 16 GiB replaced by Crucial 8 GiB, plus an owner-recorded scratch.
4. Open the public signature check. For a generic object, choose its photo workflow and shoot the same side at each checkpoint.

## Design

Canva’s homepage keeps quick create, search and recent work easy to reach. ProofScan uses those patterns for its Create menu, keyboard-searchable workspace and status-filtered verification library. The phone layout moves primary destinations into a bottom navigation bar. [Canva homepage guide](https://www.canva.com/design-school/resources/navigating-the-homepage/), [Canva mobile navigation](https://www.canva.com/en_gb/help/navigate-canva-mobile-app/)

Pinterest’s boards and sections make saved items easy to browse and open in context. ProofScan applies that principle to a list or grid of verification records, report previews in a side panel and private photo previews beside their results. [Pinterest board guide](https://help.pinterest.com/en-gb/article/boards), [Pinterest board sections](https://help.pinterest.com/en/article/create-a-board-section)

Before signing in, you can switch layouts, search and open the clearly labeled example reports. Press Ctrl or Command + K to search. The seller workflow keeps listing claims in view and groups consent, collection, review and sharing. Handoffs show which checkpoint is next.

The same responsive web workspace runs in the browser and the configured Tauri and Expo webviews. Device scanning stays in native screens that use the shared colors and control shapes in `packages/design-tokens`.

The workspace images were produced with built-in ImageGen. The prompt for `apps/web/public/workspace/verify.webp` requested an unbranded silver laptop on a lilac studio backdrop, angled to the left with an unlit screen and space for the card copy. The prompt for `apps/web/public/workspace/handoff.webp` requested two people handing over an unbranded graphite camera on a celadon backdrop, with the hands and camera toward the right.

## Platform coverage

| Platform | Behavior |
| --- | --- |
| Web | Buyer, guest seller, report check and operator screens |
| Windows | Read-only CIM hardware scan and Tauri source |
| macOS | Tauri source for model, memory and available CPU name. Native runtime validation is pending. |
| Android and iOS | Expo seller client for model, supported memory, camera, consent and report decisions. Physical-device validation and store attestation are pending. |
