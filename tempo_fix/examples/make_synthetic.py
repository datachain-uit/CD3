# -*- coding: utf-8 -*-
"""Regenerate the synthetic enrollment table used by the demo outputs in this folder:
    python tempo_fix/examples/make_synthetic.py  -> examples/synthetic_enrollments.csv (~22 MB)
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from tempo_fix.tests.conftest import make_enrollments

if __name__ == '__main__':
    out = os.path.join(os.path.dirname(__file__), 'synthetic_enrollments.csv')
    make_enrollments(n_offerings=600, seed=1).to_csv(out, index=False)
    print('written', out)
