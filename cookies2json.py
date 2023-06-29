import re
import json

import pyperclip

cookies = pyperclip.paste()
json.dump(
    {
        match.group(1).strip(): match.group(2).strip()
        for match in iter(re.compile(r'(.+?)=(.+?);').scanner(cookies).match, None)
    },
    open('cookies.json', 'w', encoding='utf-8'),
    indent=4
)