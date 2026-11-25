import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Guide:
    title: str
    href: str
    terms: tuple[str, ...]
    text: str


GUIDES = (
    Guide(
        "About ProofScan",
        "/about",
        (
            "what is proofscan",
            "what does proofscan",
            "about proofscan",
            "what can you do",
            "how does proofscan work",
            "proofscan",
        ),
        "ProofScan helps you check a used device before you pay. A seller collects supported hardware readings and exterior photos, reviews them, and chooses whether to share a signed report. You can compare fresh evidence at pickup or after a handoff.",
    ),
    Guide(
        "Open a seller link",
        "/help",
        (
            "seller link",
            "verification link",
            "expired link",
            "private link",
            "send a link",
            "open a link",
            "link expires",
        ),
        "Create a verification in the workspace and share the complete private seller link. Open it on the device being checked. If the link expired, ask the buyer to create a fresh verification.",
    ),
    Guide(
        "Capture exterior photos",
        "/help#mobile",
        (
            "photo",
            "photos",
            "camera",
            "picture",
            "pictures",
            "blur",
            "blurry",
            "front and back",
            "lighting",
        ),
        "New purchase checks require front and back photos. If the device is a phone, share a camera link to a second device, take the pictures there, then refresh photos in the original scanner. Use even light and retake blurry or obstructed views.",
    ),
    Guide(
        "Check a report signature",
        "/verify",
        (
            "signature",
            "signed report",
            "signatures",
            "report id",
            "validity",
            "signature verified",
            "tamper",
            "report authentic",
        ),
        "Open Check a report and enter the report ID to see whether its signature is valid. A valid signature confirms report integrity. Inspect the physical device separately before accepting it.",
    ),
    Guide(
        "Compare evidence at pickup",
        "/help",
        (
            "pickup",
            "pick up",
            "recheck",
            "swapped",
            "wrong device",
            "collect in person",
            "same device",
            "different device",
            "device has changed",
            "damaged since",
            "before i accept",
        ),
        "From the original signed report, create a private pickup recheck. Collect fresh readings and matching photos with the device in hand. ProofScan shows differences in available readings and flags photos worth a closer look.",
    ),
    Guide(
        "Record a handoff",
        "/handoffs",
        (
            "handoff",
            "hand over",
            "checkout",
            "return condition",
            "baseline",
            "when it comes back",
            "equipment",
        ),
        "Record the starting condition and photos, then add new evidence when the item comes back. Use the same views and distance to make the before-and-after photos easier to compare.",
    ),
    Guide(
        "Privacy in ProofScan",
        "/privacy",
        (
            "privacy",
            "retention",
            "who can see",
            "who sees",
            "stored",
            "delete photos",
            "sharing",
            "my data",
            "private reports",
        ),
        "The seller chooses whether to share a purchase report. Detailed evidence is then available to the buyer. Photos and visual descriptors expire under the workspace retention settings. The public signature lookup shows validity information.",
    ),
    Guide(
        "Use a device collector",
        "/help#desktop",
        (
            "desktop collector",
            "powershell",
            "scan ticket",
            "collector",
            "windows scan",
            "macos scan",
            "scan file",
            "scan a phone",
            "scan my phone",
            "scan a laptop",
            "scan my laptop",
        ),
        "Open the seller link on the device being checked. For a supported phone, follow the scanner instructions in the mobile app. For Windows or macOS, select the operating system on the seller page and use the scan ticket in the supported collector. Review the readings before sharing.",
    ),
    Guide(
        "Choose a ProofScan app",
        "/home#download",
        (
            "download",
            "install proofscan",
            "platforms",
            "get proofscan",
            "app availability",
            "mobile app",
        ),
        "Use ProofScan in the browser to manage requests and reports. The downloads page shows the Windows collector and current app availability for macOS, Android, and iOS.",
    ),
    Guide(
        "Compare devices in Buyer Chat",
        "/advisor",
        (
            "buyer chat",
            "chat history",
            "compare my",
            "compare devices",
            "how do you compare",
            "saved listings",
        ),
        "Buyer Chat can compare available readings in your shared reports and optionally include listings you saved. When a report has no measurement for your priority, the comparison leaves it unavailable.",
    ),
    Guide(
        "What to check before buying used",
        "/home#how-it-works",
        (
            "what should i check",
            "buying used",
            "secondhand",
            "how to inspect",
            "test a used",
            "condition check",
        ),
        "Compare the listing with the model, memory, storage and battery health when available. Inspect the screen, ports and casing, test the device in person, and ask about any mismatch or missing measurement before paying.",
    ),
)


def find_guides(question: str) -> list[Guide]:
    ranks = [
        (
            max(
                (
                    len(term)
                    for term in guide.terms
                    if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", question)
                ),
                default=0,
            ),
            guide,
        )
        for guide in GUIDES
    ]
    return [guide for score, guide in sorted(ranks, key=lambda item: item[0], reverse=True)[:2] if score]
