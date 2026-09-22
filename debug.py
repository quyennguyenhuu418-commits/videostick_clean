import sys
sys.path.insert(0, 'kịch bản/scripthunter')
from script_generator import ScriptGenerator
from database import Database, Trend

gen = ScriptGenerator()
trend = Trend(platform='reddit', source_id='t1', title='Test Topic', content='A story', viral_score=0.7, hook_type='mystery', niche='true_crime')
script = gen.generate_script(trend, target_duration=12)
print('Duration:', script.duration_minutes, 'min')
print('Total words:', len(script.content.split()))

import json
struct = json.loads(script.structure)
for s in struct['sections']:
    name = s['name']
    words = s['words']
    duration = s['duration']
    print('  ' + name + ': ' + str(words) + ' words, ' + str(duration) + 's')
