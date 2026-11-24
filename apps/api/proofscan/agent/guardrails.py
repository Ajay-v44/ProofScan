import re
import unicodedata

RESTRICTED = re.compile(
    r"\b(?:api[ -]?keys?|passwords?|credentials?|company secrets?|private keys?|access tokens?|"
    r"system prompts?|developer messages?|hidden (?:prompt|instructions?)|chain of thought|"
    r"internal (?:docs|data|logs|metrics|config|configuration|instructions|revenue|roadmap)|"
    r"other (?:users?|accounts?|customers?)|another (?:user|account|customer)|"
    r"all (?:users?|customers?|accounts?)|environment variables?|database dumps?|"
    r"bypass (?:the )?(?:rules|guardrails)|ignore (?:all |the |your )?(?:previous |prior )?instructions?)\b"
)

DEVICE_PATTERNS = (
    re.compile(r"\b(iphone[ -]?(?:se|air|[1-9][0-9]?[a-e]?)(?: pro max| pro| plus| mini| max)?)\b"),
    re.compile(r"\b((?:google +)?pixel [1-9][0-9]?[a-e]?(?: pro fold| pro xl| pro| xl| fold)?)\b"),
    re.compile(
        r"\b((?:(?:samsung +)?galaxy |samsung +(?=s[0-9]))(?:[sazm][0-9]{1,3}(?: ultra| plus| fe| ?\+)?|(?:z )?(?:fold|flip) ?[0-9]{1,2}))(?!\w)"
    ),
    re.compile(r"\b(oneplus (?:nord (?:ce ?)?[0-9]{1,2}(?: lite)?|[0-9]{1,2}r?(?: pro| t)?))\b"),
    re.compile(r"\b((?:xiaomi |redmi note |poco [xf])[0-9]{1,2}(?: pro\+| pro plus| pro| ultra)?)\b"),
    re.compile(
        r"\b((?:apple +)?macbook (?:air|pro)(?: m[1-9](?: pro| max)?)?|thinkpad [txle][0-9]{1,3}(?:s)?(?: gen [0-9]{1,2})?)\b"
    ),
)


def normalized(text: str) -> str:
    return " ".join(
        "".join(
            char for char in unicodedata.normalize("NFKC", text) if unicodedata.category(char) != "Cf"
        )
        .casefold()
        .split()
    )


def sensitive_request(text: str) -> bool:
    return bool(RESTRICTED.search(normalized(text)))


def device_models(text: str) -> list[str]:
    text = normalized(text)
    matches = sorted(
        (match.start(), match[1]) for pattern in DEVICE_PATTERNS for match in pattern.finditer(text)
    )
    names = [canonical_device(name) for _, name in matches]
    return list(dict.fromkeys(names))


def canonical_device(name: str) -> str:
    name = re.sub(r"^(?:google|apple|samsung galaxy|galaxy) ", "", name)
    if re.match(r"^(?:[sazm]\d|(?:z )?(?:fold|flip))", name) or name.startswith("samsung s"):
        name = "galaxy " + name.removeprefix("samsung ")
    name = re.sub(r"^iphone[ -]?(?=\d|se\b|air\b)", "iphone ", name)
    name = re.sub(r"^(galaxy [a-z]\d+) ?\+$", r"\1 plus", name)
    return name


def device_title(name: str) -> str:
    brands = {"iphone": "iPhone", "macbook": "MacBook", "oneplus": "OnePlus", "thinkpad": "ThinkPad"}
    return " ".join(
        brands.get(word, word.upper() if word in {"se", "fe", "xl", "ce"} else word.title())
        for word in name.split()
    )
