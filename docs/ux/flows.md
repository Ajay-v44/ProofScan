# UX and demo

## Demo script

1. From the buyer workspace, create a verification for a laptop advertised with 16 GiB memory, a 1,000 GB drive and at least 85% battery health.
2. Open the private link in a different browser context. Show the consent screen and how it controls collection.
3. For a real device, download a ticket and use the Windows collector on the device being sold. Import the scan on the seller page and record clear front and back photos. For the matching simulator, enable the simulator and select its matching fixture.
4. Review the captured readings and claim comparisons. Share the report, return to the buyer workspace, refresh, and open the report.
5. Show the public signature check. Then demonstrate the mismatched fixture and decline sharing from a separate request.

## Handoff demo

1. Open Handoffs and create a simulator handoff. Start and record the baseline.
2. Optionally create the private acceptance link, open it in a separate browser session and accept. Refresh the owner page and mark the asset as handed off.
3. Start the return check and record the return. The simulated comparison shows Samsung 16 GiB replaced by Crucial 8 GiB, plus an owner-recorded scratch.
4. Open the public signature check. For a generic object, choose its photo workflow and follow the suggested views at both checkpoints.

## Picture guidance and pickup rechecks

- For a new purchase request, use the seller link on the actual device to collect the supported internal readings. Capture its front and back through the same request. The camera offers framing and lighting tips. The server can ask for a clearer photo before saving a view. Add sides or detail photos when they show relevant wear.
- When the device under inspection is a phone, select **Share camera link** in the Expo scanner and open it on a second phone or tablet. Use a workspace address reachable from both devices. The link can submit photos for up to 15 minutes. The original device keeps control of readings and sharing. After capture, select **Refresh photos** on the original scanner and continue there.
- At pickup, open the original signed report and select **Create pickup recheck link**. Keep the link with the buyer, use it to take fresh photos, and run the supported internal scan on the device being offered. After sharing, open the new report to review hardware differences and matching-angle pictures. A link authorizes collection. Control of the phone or computer and the physical inspection stay with the buyer.
- For a handoff, record the suggested views of the item when it leaves and returns. During return capture, the app shows the baseline image for that angle and gives feedback after the new photo is saved. Take another photo if the framing, clarity, or lighting makes a comparison difficult.
- ProofScan stores a local 256-value image descriptor together with each processed photo. Comparison uses the descriptor as a coarse visual cue, then aligns matching features and checks for local changes. Exact reuse of saved image bytes is flagged. Lighting, reflection and different framing can trigger a review or hide damage. Matching photos and readings cannot establish the identity of a physical unit. Inspect the item before paying or accepting it. [OpenCV feature matching](https://docs.opencv.org/3.4.6/d1/de0/tutorial_py_feature_homography.html)
- Private photos and descriptors expire together according to server evidence retention. The signed report keeps the evidence digests and recorded findings after the photos expire.

## Design

Canva’s homepage keeps quick create, search and recent work easy to reach. ProofScan uses those patterns for its Create menu, keyboard-searchable workspace and status-filtered verification library. The phone layout moves primary destinations into a bottom navigation bar. [Canva homepage guide](https://www.canva.com/design-school/resources/navigating-the-homepage/), [Canva mobile navigation](https://www.canva.com/en_gb/help/navigate-canva-mobile-app/)

Pinterest’s boards and sections make saved items easy to browse and open in context. ProofScan applies that principle to a list or grid of verification records, report previews in a side panel and private photo previews beside their results. [Pinterest board guide](https://help.pinterest.com/en-gb/article/boards), [Pinterest board sections](https://help.pinterest.com/en/article/create-a-board-section)

Before signing in, you can switch layouts, search and open the clearly labeled example reports. Press Ctrl or Command + K to search. The seller workflow keeps listing claims in view and groups consent, collection, review and sharing. Handoffs show which checkpoint is next.

The overview, verifications, handoffs, Buyer Chat, and private reports share the same workspace layout. Desktop uses a side navigation and a single content width. On smaller screens, four primary destinations move to the bottom bar. Seller, camera, acceptance, and public signature pages use a focused layout. The web footer links to About, Help, and Privacy. About shows the version from the current web, Expo, or Tauri configuration.

The browser and the configured desktop and Expo WebViews use the same responsive workspace. The native device scanners use the shared palette in `packages/design-tokens` and respect each platform’s safe areas and touch targets. Expo supports rotation and iPad layouts. Test a real device and large text before signing off. [W3C guidance on reflow and focus](https://www.w3.org/WAI/WCAG22/Understanding/reflow) · [Apple layout guidance](https://developer.apple.com/design/human-interface-guidelines/layout)

ImageGen produced the ProofScan mark and the device inspection photograph. The web marks live in `apps/web/public/brand` and `apps/web/app`. Expo launcher and splash assets and Tauri desktop icons use the same folded P artwork.

## Platform coverage

| Platform | Behavior |
| --- | --- |
| Web | Buyer, guest seller, report check and operator screens |
| Windows | Read-only CIM hardware scan and Tauri source |
| macOS | Tauri source for model, memory and available CPU name. Native runtime validation is pending. |
| Android and iOS | Expo seller client for model, supported memory, camera, consent and report decisions. Physical-device validation and store attestation are pending. |

## Account pages

Sign-in, sign-up, password recovery, and profile use separate routes. The desktop layout places ProofScan’s device photography beside the form. At smaller widths the image becomes a shallow banner so the form remains easy to reach. The photos and focus states use the same navy and apricot palette as the public presentation.

- Authentication returns users to the workspace, handoffs, Buyer Chat, profile, or operator area that asked them to sign in. Starting a verification while signed out reopens the verification sheet after sign-in.
- The verification sheet keeps the device name and advertised specs together. After creation it shows the private seller link, expiry, copy action and open-link action. The public report lookup shows where to find the ID and retains the detailed signature result.
- Profile stores a display name and shows the sign-in address and recovery method. Local users can generate a one-time recovery code and save it separately from their password.
- The browser, Tauri workspace, and Expo workspace use the same pages. The Expo scanner shows progress while opening a seller link or removing a saved session. The Tauri collector offers a keyboard-accessible file picker and shows the name of the current scan ticket.

The account redesign passed web lint, workspace type checks, the production web and Tauri frontend builds, and the Android and iOS Expo exports. The API passed Ruff, mypy and 67 tests against disposable PostgreSQL with pgvector. Alembic applied the account migration and found no pending schema changes. Playwright passed 14 tests, including account recovery and verification at phone and desktop widths. The physical Windows collector test was skipped. The Tauri picker passed a browser check for keyboard focus, ticket replacement, and 320 px reflow. Live Supabase recovery email and physical native keyboard and password-manager behavior still need acceptance testing.
