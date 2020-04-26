# ----------------------------------------------------------------------------
# Copyright (c) 2020, Franck Lejzerowicz.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import pandas as pd
from os.path import basename, isfile, splitext
import multiprocessing

from routine_qiime2_analyses._routine_q2_xpbs import print_message
from routine_qiime2_analyses._routine_q2_io_utils import (
    get_metrics, get_job_folder,
    get_analysis_folder,
    get_main_cases_dict,
    write_main_sh,
    read_meta_pd
)
from routine_qiime2_analyses._routine_q2_metadata import (
    check_metadata_cases_dict,
    check_metadata_testing_groups
)
from routine_qiime2_analyses._routine_q2_cmds import (
    get_new_meta_pd, get_case,
    write_diversity_beta_group_significance,
    add_q2_types_to_meta, get_metric,
    check_absence_mat
)


def run_multi_perm(odir: str, tsv: str, meta_pd: pd.DataFrame, cur_sh: str,
                   case_: str, testing_group: str, mat_qza: str, case_var: str,
                   case_vals: list, force: bool) -> None:
    """
    Run beta-group-significance: Beta diversity group significance.
    https://docs.qiime2.org/2019.10/plugins/available/diversity/beta-group-significance/
    (in-loop function).

    :param odir: output analysis directory.
    :param tsv: features table input to the beta diversity matrix.
    :param meta_pd: metadata table.
    :param cur_sh: input bash script file.
    :param case_:
    :param testing_group:
    :param mat_qza:
    :param case_var:
    :param case_vals:
    :param force: Force the re-writing of scripts for all commands.
    """
    remove = True
    qza = '%s.qza' % splitext(tsv)[0]
    with open(cur_sh, 'w') as cur_sh_o:
        case = '%s__%s' % (case_, testing_group)
        case = case.replace(' ', '_')
        cur_rad = odir + '/' + basename(tsv).replace('.tsv', '_%s' % case)
        new_meta = '%s.meta' % cur_rad
        new_qza = '%s.qza' % cur_rad
        new_qzv = '%s_permanova.qzv' % cur_rad
        new_mat_qza = odir + '/' + basename(mat_qza).replace('.qza', '_%s.qza' % case)
        print('>', case)
        print('  -', new_qzv)
        print('  -', new_mat_qza)
        if force or not isfile(new_qzv):
            new_meta_pd = get_new_meta_pd(meta_pd, case, case_var, case_vals)
            if new_meta_pd[testing_group].unique().size > 1:
                add_q2_types_to_meta(new_meta_pd, new_meta)
                write_diversity_beta_group_significance(new_meta, mat_qza, new_mat_qza,
                                                        qza, new_qza, testing_group,
                                                        new_qzv, cur_sh_o)
                remove = False
    with open(cur_sh) as f:
        for line in f:
            print('*****', line.strip())

    if remove:
        os.remove(cur_sh)


def run_single_perm(odir: str, tsv: str, meta_pd: pd.DataFrame, cur_sh: str,
                    case_: str, testing_group: str, mat_qza: str, case_var: str,
                    case_vals: list, force: bool) -> None:
    """
    Run beta-group-significance: Beta diversity group significance.
    https://docs.qiime2.org/2019.10/plugins/available/diversity/beta-group-significance/
    (in-loop function).

    :param odir: output analysis directory.
    :param tsv: features table input to the beta diversity matrix.
    :param meta_pd: metadata table.
    :param cur_sh: input bash script file.
    :param case_:
    :param testing_group:
    :param mat_qza:
    :param case_var:
    :param case_vals:
    :param force: Force the re-writing of scripts for all commands.
    """
    remove = True
    qza = '%s.qza' % splitext(tsv)[0]
    with open(cur_sh, 'w') as cur_sh_o:
        case = '%s__%s' % (case_, testing_group)
        case = case.replace(' ', '_')
        cur_rad = odir + '/' + basename(tsv).replace('.tsv', '_%s' % case)
        new_meta = '%s.meta' % cur_rad
        new_qza = '%s.qza' % cur_rad
        new_qzv = '%s_permanova.qzv' % cur_rad
        new_mat_qza = odir + '/' + basename(mat_qza).replace('.qza', '_%s.qza' % case)
        print('>', case)
        print('  -', new_qzv)
        print('  -', new_mat_qza)
        if force or not isfile(new_qzv):
            new_meta_pd = get_new_meta_pd(meta_pd, case, case_var, case_vals)
            if new_meta_pd[testing_group].unique().size > 1:
                add_q2_types_to_meta(new_meta_pd, new_meta)
                write_diversity_beta_group_significance(new_meta, mat_qza, new_mat_qza,
                                                        qza, new_qza, testing_group,
                                                        new_qzv, cur_sh_o)
                remove = False

    with open(cur_sh) as f:
        for line in f:
            print('*****', line.strip())
    if remove:
        os.remove(cur_sh)


def run_permanova(i_datasets_folder: str, datasets: dict, betas: dict, main_testing_groups: tuple,
                  p_perm_groups: str, force: bool, prjct_nm: str, qiime_env: str, chmod: str) -> None:
    """
    Run beta-group-significance: Beta diversity group significance.
    https://docs.qiime2.org/2019.10/plugins/available/diversity/beta-group-significance/
    Main per-dataset looper for the PERMANOVA tests on beta diversity matrices.

    :param i_datasets_folder: Path to the folder containing the data/metadata subfolders.
    :param datasets: list of datasets.
    :param betas: beta diversity matrices.
    :param main_testing_groups: groups to test.
    :param p_perm_groups: groups to subset.
    :param force: Force the re-writing of scripts for all commands.
    :param prjct_nm: Nick name for your project.
    :param qiime_env: qiime2-xxxx.xx conda environment.
    :param chmod: whether to change permission of output files (defalt: 775).
    """
    job_folder2 = get_job_folder(i_datasets_folder, 'permanova/chunks')
    beta_metrics = get_metrics('beta_metrics')

    main_cases_dict = get_main_cases_dict(p_perm_groups)

    jobs = []
    all_sh_pbs = {}
    first_print = 0
    for dat, tsv_meta_pds in datasets.items():

        tsv, meta = tsv_meta_pds
        meta_pd = read_meta_pd(meta)
        meta_pd = meta_pd.set_index('sample_name')
        mat_qzas = betas[dat][meta]

        cases_dict = check_metadata_cases_dict(meta, meta_pd, dict(main_cases_dict), 'PERMANOVA')
        testing_groups = check_metadata_testing_groups(meta, meta_pd, main_testing_groups, 'PERMANOVA')

        absence_mat = check_absence_mat(mat_qzas, first_print, 'PERMANOVA')
        if absence_mat:
            continue

        odir = get_analysis_folder(i_datasets_folder, 'permanova/%s' % dat)
        for mat_qza in mat_qzas:
            metric = get_metric(beta_metrics, mat_qza)
            out_sh = '%s/run_beta_group_significance_%s_%s.sh' % (job_folder2, dat, metric)
            for case_var, case_vals_list in cases_dict.items():
                testing_groups_case_var = list(set(testing_groups + [case_var]))
                for case_vals in case_vals_list:
                    case_ = get_case(case_vals, metric, case_var).replace(' ', '_')
                    for testing_group in testing_groups_case_var:
                        if testing_group == 'ALL':
                            continue
                        cur_sh = '%s/run_beta_group_significance_%s_%s_%s.sh' % (
                            job_folder2, dat, case_, testing_group)
                        cur_sh = cur_sh.replace(' ', '-')
                        all_sh_pbs.setdefault((dat, out_sh), []).append(cur_sh)
                        run_single_perm(odir, tsv, meta_pd, cur_sh, case_, testing_group,
                                        mat_qza, case_var, case_vals, force)

                        # p = multiprocessing.Process(
                        #     target=run_multi_perm,
                        #     args=(odir, tsv, meta_pd, cur_sh, case_, testing_group,
                        #           mat_qza, case_var, case_vals, force))
                        # p.start()
                        # jobs.append(p)
    # for j in jobs:
    #     j.join()

    job_folder = get_job_folder(i_datasets_folder, 'permanova')
    main_sh = write_main_sh(job_folder, '3_run_beta_group_significance', all_sh_pbs,
                            '%s.prm' % prjct_nm, '2', '1', '1', '1', 'gb',
                            qiime_env, chmod)
    if main_sh:
        if p_perm_groups:
            print("# PERMANOVA (groups config in %s)" % p_perm_groups)
        else:
            print("# PERMANOVA")
        print_message('', 'sh', main_sh)
