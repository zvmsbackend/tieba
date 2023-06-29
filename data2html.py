import json

import tieba

data = json.load(open('data.json', encoding='utf-8'))
tieba.write_file(
    data['title'], 
    data['result'], 
    tieba.determine_filename(data['title'], None)
)