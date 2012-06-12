#/bin/bash
PYTHONPATH=../:$PYTHONPATH FUNNEL_CONFIG=../config.cfg nosetests $@
