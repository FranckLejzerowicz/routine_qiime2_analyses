# ----------------------------------------------------------------------------
# Copyright (c) 2020, Franck Lejzerowicz.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import yaml
import pandas as pd
import multiprocessing
from os.path import basename, dirname, isdir, isfile, splitext

from routine_qiime2_analyses._routine_q2_xpbs import xpbs_call
from routine_qiime2_analyses._routine_q2_io_utils import get_job_folder, get_analysis_folder, run_import, run_export


def run_alpha(i_folder: str, datasets, alpha_metrics: list,
              wol_trees: dict, force: bool, prjct_nm: str, qiime_env: str) -> dict:

    print('# Calculate alpha diversity indices')
    job_folder = get_job_folder(i_folder, 'alpha')
    job_folder2 = get_job_folder(i_folder, 'alpha/chunks')

    written = 0
    diversities = {}
    run_pbs = '%s/1_run_alpha.sh' % job_folder
    with open(run_pbs, 'w') as o:
        for dataset, files_lists in datasets.items():
            if dataset not in diversities:
                diversities[dataset] = {}
            out_sh = '%s/run_alpha_%s.sh' % (job_folder2, dataset)
            out_pbs = '%s.pbs' % splitext(out_sh)[0]
            with open(out_sh, 'w') as sh:
                for files_list in files_lists:
                    qza = '%s.qza' % splitext(files_list[0])[0]
                    meta = files_list[1]
                    divs = [meta]
                    for metric in alpha_metrics:
                        odir = get_analysis_folder(i_folder, 'alpha/%s' % dataset)
                        out_fp = '%s/%s_%s.qza' % (odir, basename(splitext(qza)[0]), metric)
                        divs.append(out_fp)
                        if force or not isfile(out_fp):
                            if metric == 'faith_pd':
                                cmd = [
                                    'qiime', 'diversity', 'alpha-phylogenetic',
                                    '--i-table', qza,
                                    '--i-phylogeny', wol_trees[dataset],
                                    '--p-metric', metric,
                                    '--o-alpha-diversity', out_fp]
                            else:
                                cmd = [
                                    'qiime', 'diversity', 'alpha',
                                    '--i-table', qza,
                                    '--p-metric', metric,
                                    '--o-alpha-diversity', out_fp]
                            sh.write('echo "%s"\n' % ' '.join(cmd))
                            sh.write('%s\n' % ' '.join(cmd))
                            written += 1
                    diversities[dataset][qza] = divs
            if written:
                xpbs_call(out_sh, out_pbs, '%s.mg.lph.%s' % (prjct_nm, dataset), qiime_env,
                          '4', '1', '1', '1', 'gb')
                o.write('qsub %s\n' % out_pbs)
            else:
                print('\nNothing written in', out_sh, '--> removed')
                os.remove(out_sh)
    if written:
        print('[TO RUN] sh', run_pbs)
    return diversities


def merge_meta_alpha(i_folder: str, diversities: dict,
                     force: bool, prjct_nm: str, qiime_env: str):
    job_folder = get_job_folder(i_folder, 'alpha')
    job_folder2 = get_job_folder(i_folder, 'alpha/chunks')

    print('# Merge alpha diversity indices to metadata')
    written = 0
    to_export = []
    run_pbs = '%s/2_run_merge_alphas.sh' % job_folder
    with open(run_pbs, 'w') as o:
        for dataset in diversities:
            out_sh = '%s/run_merge_alpha_%s.sh' % (job_folder2, dataset)
            out_pbs = '%s.pbs' % splitext(out_sh)[0]
            with open(out_sh, 'w') as sh:
                for qza, divs in diversities[dataset].items():
                    meta = divs[0]
                    rad = splitext(qza)[0]
                    divs = divs[1:]
                    out_fp = '%s_alphas.qzv' % rad.replace('/data/', '/metadata/').replace('/tab_', '/meta_')
                    if force or not isfile(out_fp):
                        if not isdir(dirname(out_fp)):
                            os.makedirs(dirname(out_fp))
                        to_export.append(out_fp)
                        cmd = [
                            'qiime', 'metadata', 'tabulate',
                            '--o-visualization', out_fp,
                            '--m-input-file', meta]
                        for div in divs:
                            cmd.extend(['--m-input-file', div])
                        sh.write('echo "%s"\n' % ' '.join(cmd))
                        sh.write('%s\n' % ' '.join(cmd))
                        written += 1
            if written:
                xpbs_call(out_sh, out_pbs, '%s.mg.mrg.lph.%s' % (prjct_nm, dataset), qiime_env,
                          '2', '1', '1', '150', 'mb')
                o.write('qsub %s\n' % out_pbs)
            else:
                print('\nNothing written in', out_sh, '--> removed')
                os.remove(out_sh)
    if written:
        print('[TO RUN] sh', run_pbs)
    return to_export


def export_meta_alpha(i_folder: str, to_export: list,
                      prjct_nm: str, qiime_env: str):

    print('# Export alpha diversity indices to metadata')
    job_folder = get_job_folder(i_folder, 'alpha')
    out_sh = '%s/3_run_merge_alpha_export.sh' % job_folder
    out_pbs = '%s.pbs' % splitext(out_sh)[0]
    with open(out_sh, 'w') as sh:
        for export in to_export:
            out_dir = splitext(export)[0]
            sh.write('\nqiime tools export --input-path %s --output-path %s\n' % (export, out_dir))
            sh.write('mv %s/metadata.tsv %s.tsv\n' % (out_dir, out_dir))
            sh.write('rm -rf %s %s\n' % (out_dir, export))
    xpbs_call(out_sh, out_pbs, '%s.xprt.exp.lph' % prjct_nm, qiime_env,
              '2', '1', '1', '150', 'mb')
    print('[TO RUN] qsub', out_pbs)


def run_correlations(i_folder: str, datasets: dict, diversities: dict,
                     force: bool, prjct_nm: str, qiime_env: str):


    print('# Correlate numeric metadata variables with alpha diversity indices')
    job_folder = get_job_folder(i_folder, 'alpha_correlations')
    job_folder2 = get_job_folder(i_folder, 'alpha_correlations/chunks')
    odir = get_analysis_folder(i_folder, 'alpha_correlations')
    written = 0
    run_pbs = '%s/4_run_alpha_correlation.sh' % job_folder
    with open(run_pbs, 'w') as o:
        for dat, tsvs_metas_list in datasets.items():
            for tsv, meta in tsvs_metas_list:
                for meth in ['spearman']:
                    out_sh = '%s/run_alpha_correlation_%s.sh' % (job_folder2, dat)
                    out_pbs = '%s.pbs' % splitext(out_sh)[0]
                    with open(out_sh, 'w') as sh:
                        for qza in diversities[dat]['%s.qza' % splitext(tsv)[0]][1:]:
                            out_fp = qza.replace('.qza', '.qzv').replace('/alpha/', '/alpha_correlations/')
                            if force or not isfile(out_fp):
                                if not isdir(dirname(out_fp)):
                                    os.makedirs(dirname(out_fp))
                                cmd = [
                                    'qiime', 'diversity', 'alpha-correlation',
                                    '--i-alpha-diversity', qza,
                                    '--p-method', meth,
                                    '--m-metadata-file', meta,
                                    '--o-visualization', out_fp]
                                sh.write('echo "%s"\n' % ' '.join(cmd))
                                sh.write('%s\n' % ' '.join(cmd))
                                written += 1
                    if written:
                        xpbs_call(out_sh, out_pbs, '%s.lphcrr.%s' % (prjct_nm, dat), qiime_env,
                                  '10', '1', '1', '1', 'gb')
                        o.write('qsub %s\n' % out_pbs)
                    else:
                        print('\nNothing written in', out_sh, '--> removed')
                        os.remove(out_sh)
    if written:
        print('[TO RUN] sh', run_pbs)


def run_volatility(i_folder: str, datasets: dict, p_longi_column: str,
                   force: bool, prjct_nm: str, qiime_env: str) -> None:

    print('# Longitudinal change in alpha diversity indices')
    job_folder = get_job_folder(i_folder, 'longitudinal')
    job_folder2 = get_job_folder(i_folder, 'longitudinal/chunks')
    written = 0
    first_print = 0
    first_print2 = 0
    run_pbs = '%s/5_run_volatility.sh' % job_folder
    with open(run_pbs, 'w') as o:
        for dat, tsvs_metas_list in datasets.items():
            for tsv, meta in tsvs_metas_list:
                meta_alphas = '%s_alphas.tsv' % splitext(meta)[0]
                if not isfile(meta_alphas):
                    if not first_print:
                        print('\nWarning: First make sure you run alpha -> alpha merge -> alpha export'
                              ' before running volatility\n\t(if you need the alpha as a response variable)!')
                        first_print += 1
                    # continue
                with open(meta) as f:
                    for line in f:
                        break
                time_point = [x for x in line.strip().split('\t') if p_longi_column in x][0]
                if not time_point:
                    if not first_print2:
                        print('Variable %s not in metadata %s\n' % (p_longi_column, meta_alphas))
                        first_print2 += 1
                    continue
                out_sh = '%s/run_volatility_%s.sh' % (job_folder2, dat)
                out_pbs = '%s.pbs' % splitext(out_sh)[0]
                with open(out_sh, 'w') as sh:
                    odir = get_analysis_folder(i_folder, 'longitudinal/%s' % dat)
                    out_fp = '%s/%s_volatility.qzv' % (odir, dat)
                    if force or not isfile(out_fp):
                        if not isdir(dirname(out_fp)):
                            os.makedirs(dirname(out_fp))
                        cur_cmd = [
                            'qiime', 'longitudinal', 'volatility',
                            '--m-metadata-file', meta_alphas,
                            '--p-state-column', '"%s"' % time_point,
                            '--p-individual-id-column', '"host_subject_id"',
                            '--o-visualization', out_fp]
                        sh.write('echo "%s"\n' % ' '.join(cur_cmd))
                        sh.write('%s\n' % ' '.join(cur_cmd))
                        written += 1
                if written:
                    xpbs_call(out_sh, out_pbs, '%s.vltlt.%s' % (prjct_nm, dat), qiime_env,
                              '2', '1', '1', '100', 'mb')
                    o.write('qsub %s\n' % out_pbs)
                else:
                    print('\nNothing written in', out_sh, '--> removed')
                    os.remove(out_sh)
    if written:
        print('[TO RUN] sh', run_pbs)


def run_alpha_group_significance(i_folder: str, diversities: dict, p_perm_groups: str, alpha_metrics: list,
                                 force: bool, prjct_nm: str, qiime_env: str):

    print("# Kruskal-Wallis (groups config in %s)" % p_perm_groups)
    def run_multi_kw(odir, meta_pd, div_qza, case, case_var, case_vals, sh):

        cur_rad = odir + '/' + basename(div_qza).replace('.qza', '_%s' % case)
        new_qzv = '%s_kruskal-wallis.qzv' % cur_rad

        new_meta = '%s.meta' % cur_rad
        new_tsv = '%s.tsv' % cur_rad
        new_div = '%s.qza' % cur_rad

        if force or not isfile(new_qzv):
            if 'ALL' in case:
                new_meta_pd = meta_pd.copy()
                sh.write('cp %s %s\n' % (div_qza, new_div))
            else:
                if len([x for x in case_vals if '>' in x or '<' in x]):
                    new_meta_pd = meta_pd.copy()
                    for case_val in case_vals:
                        if case_val[0] == '>':
                            new_meta_pd = new_meta_pd[new_meta_pd[case_var] >= float(case_val[1:])].copy()
                        elif case_val[0] == '<':
                            new_meta_pd = new_meta_pd[new_meta_pd[case_var] <= float(case_val[1:])].copy()
                else:
                    new_meta_pd = meta_pd[meta_pd[case_var].isin(case_vals)].copy()
                print(new_tsv)
                print(new_div)
                print(new_divfd)
                cmd = run_export(new_div, new_tsv, '')
                sh.write(cmd)
                new_tsv_pd = pd.read_csv(new_tsv, header=0, index_col=0, sep='\t')
                new_tsv_pd = new_tsv_pd.loc[new_meta_pd.index.tolist(),:]
                new_tsv_pd.reset_index().to_csv(new_tsv, index=False, sep='\t')
                cmd = run_import(new_div, new_tsv, 'AlphaDiversity')
                sh.write(cmd)
            new_meta_pd.reset_index().to_csv(new_meta, index=False, sep='\t')

            cmd = [
                'qiime diversity alpha-group-significance'
                '--i-alpha-diversity', new_div,
                '--m-metadata-file', new_meta,
                '--o-visualization', new_qzv]
            sh.write('echo "%s"\n' % ' '.join(cmd))
            sh.write('%s\n' % ' '.join(cmd))
            sh.write('rm %s' % new_meta)


    job_folder = get_job_folder(i_folder, 'alpha_group_significance')
    job_folder2 = get_job_folder(i_folder, 'alpha_group_significance/chunks')

    with open(p_perm_groups) as handle:
        cases_dict = yaml.load(handle, Loader=yaml.FullLoader)
    cases_dict.update({'ALL': [[]]})

    jobs = []
    first_print = 0
    main_sh = '%s/6_run_alpha_group_significance.sh' % job_folder
    with open(main_sh, 'w') as o:
        for dataset in diversities:
            odir = get_analysis_folder(i_folder, 'alpha_group_significance/%s' % dataset)
            out_sh = '%s/run_alpha_group_significance_%s.sh' % (job_folder2, dataset)
            out_pbs = '%s.pbs' % splitext(out_sh)[0]
            o.write('qsub %s\n' % out_pbs)
            with open(out_sh, 'w') as sh:
                for qza, divs in diversities[dataset].items():
                    meta = divs[0]
                    divs = divs[1:]
                    meta_pd = pd.read_csv(meta, header=0, index_col=0, sep='\t')
                    for div_qza in divs:
                        for metric in alpha_metrics:
                            if metric in div_qza:
                                break
                        # if not isfile(div_qza):
                        if 0:
                            if first_print:
                                print('Alpha diversity must be measured already to automatise Kruskal-Wallis tests\n'
                                      '\t(re-run this after step "1_run_alpha.sh" is done)')
                                first_print += 1
                            continue

                        for case_var, case_vals_list in cases_dict.items():
                            for case_vals in case_vals_list:
                                if len(case_vals):
                                    case = '%s_%s_%s' % (metric, case_var, '-'.join(
                                        [x.replace('<', 'below').replace('>', 'above') for x in case_vals]))
                                else:
                                    case = '%s_%s' % (metric, case_var)
                                p = multiprocessing.Process(
                                    target=run_multi_kw,
                                    args=(odir, meta_pd, div_qza, case, case_var, case_vals, sh)
                                )
                                p.start()
                                jobs.append(p)
                                print(fds)
            xpbs_call(out_sh, out_pbs, '%s.perm.%s' % (prjct_nm, dataset), qiime_env,
                      '2', '1', '1', '2', 'gb')
    for j in jobs:
        j.join()

    print('[TO RUN] sh', main_sh)