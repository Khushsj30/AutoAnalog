#!/bin/bash
sed -i 's/LEVEL=14/LEVEL=8/g' models/tsmc180nm_tt.lib
sed -i 's/+ VERSION = 3.3/* VERSION = 3.3/g' models/tsmc180nm_tt.lib
python3 -c "
content = open('python/autoanalog/simulation/results.py').read()
content = content.replace('self.dc_gain_db >= specs[\"gain_db_min\"]', 'self.dc_gain_db >= float(specs[\"gain_db_min\"])')
content = content.replace('self.gbw_hz >= specs[\"gbw_min_hz\"]', 'self.gbw_hz >= float(specs[\"gbw_min_hz\"])')
content = content.replace('self.phase_margin_deg >= specs[\"phase_margin_min_deg\"]', 'self.phase_margin_deg >= float(specs[\"phase_margin_min_deg\"])')
open('python/autoanalog/simulation/results.py', 'w').write(content)
content = open('python/autoanalog/visualization/optimization_plots.py').read()
content = content.replace('marker=\"★\"', 'marker=\"*\"')
open('python/autoanalog/visualization/optimization_plots.py', 'w').write(content)
print('All fixes applied')
"
