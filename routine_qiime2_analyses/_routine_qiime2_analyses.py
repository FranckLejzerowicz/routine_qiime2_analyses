# ----------------------------------------------------------------------------
# Copyright (c) 2020, Franck Lejzerowicz.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import sys
import subprocess
from os.path import abspath, exists, isdir, isfile

from routine_qiime2_analyses._routine_q2_io_utils import (get_prjct_nm, get_datasets,
                                                          get_run_params, summarize_songbirds,
                                                          get_analysis_folder)
from routine_qiime2_analyses._routine_q2_filter import (import_datasets, filter_rare_samples,
                                                        get_filt3d_params, explore_filtering,
                                                        deleted_non_filt)
from routine_qiime2_analyses._routine_q2_rarefy import run_rarefy
from routine_qiime2_analyses._routine_q2_phylo import shear_tree, run_sepp, get_precomputed_trees
from routine_qiime2_analyses._routine_q2_qemistree import run_qemistree
from routine_qiime2_analyses._routine_q2_taxonomy import (run_taxonomy, run_barplot, run_collapse,
                                                          make_pies, get_taxo_levels, edit_taxonomies,
                                                          get_precomputed_taxonomies,
                                                          create_songbird_feature_metadata)
from routine_qiime2_analyses._routine_q2_doc import run_doc
from routine_qiime2_analyses._routine_q2_sourcetracking import run_sourcetracking
from routine_qiime2_analyses._routine_q2_alpha import (run_alpha, merge_meta_alpha, export_meta_alpha,
                                                       run_correlations, run_volatility,
                                                       run_alpha_group_significance)
from routine_qiime2_analyses._routine_q2_beta import (run_beta, export_beta,
                                                      run_pcoas, run_biplots,
                                                      run_emperor, run_emperor_biplot,
                                                      run_empress, run_empress_biplot)
from routine_qiime2_analyses._routine_q2_decay import (run_distance_decay, distance_decay_figure)
from routine_qiime2_analyses._routine_q2_procrustes_mantel import (run_procrustes, run_mantel)
from routine_qiime2_analyses._routine_q2_deicode import run_deicode
from routine_qiime2_analyses._routine_q2_permanova import run_permanova, summarize_permanova
from routine_qiime2_analyses._routine_q2_nestedness import run_nestedness, nestedness_graphs, nestedness_nodfs
from routine_qiime2_analyses._routine_q2_adonis import run_adonis
from routine_qiime2_analyses._routine_q2_phate import run_phate
from routine_qiime2_analyses._routine_q2_songbird import run_songbird
from routine_qiime2_analyses._routine_q2_mmvec import run_mmvec
from routine_qiime2_analyses._routine_q2_mmbird import run_mmbird


def routine_qiime2_analyses(
        i_datasets: tuple,
        i_datasets_folder: str,
        project_name: str,
        p_longi_column: str,
        p_filt_threshs: str,
        p_raref_depths: str,
        eval_rarefs: bool,
        p_alpha_subsets: str,
        p_beta_subsets: str,
        p_perm_tests: tuple,
        p_beta_groups: str,
        p_nestedness_groups: str,
        p_beta_type: tuple,
        p_procrustes: str,
        p_mantel: str,
        p_distance_decay: str,
        p_collapse_taxo: str,
        p_formulas: str,
        p_doc_config: str,
        p_sourcetracking_config: str,
        p_phate_config: str,
        force: bool,
        i_classifier: str,
        i_wol_tree: str,
        i_sepp_tree: str,
        i_qemistree: str,
        p_diff_models: str,
        p_mmvec_pairs: str,
        p_mmvec_highlights: str,
        p_xmmvec: str,
        qiime_env: str,
        p_run_params: str,
        chmod: str,
        p_skip: tuple,
        gpu: bool,
        standalone: bool,
        raref: bool,
        noloc: bool,
        As: tuple,
        Bs: tuple,
        split: bool,
        dropout: bool,
        doc_phate: bool,
        filt3d: bool,
        p_filt3d_config: str,
        filt_only: bool,
        jobs: bool,
        chunkit: int) -> None:
    """
    Main qiime2 functions writer.

    :param i_datasets: Internal name identifying the datasets in the input folder.
    :param i_datasets_folder: Path to the folder containing the data/metadata subfolders.
    :param project_name: Nick name for your project.
    :param qiime_env: name of your qiime2 conda environment (e.g. qiime2-2019.10).
    :param p_alpha_subsets: Subsets for alpha diversity.
    :param p_perm_tests: Subsets for PERMANOVA.
    :param p_perm_groups: Groups to test between in each PERMANOVA subset (yml file path).
    :param p_formulas: Formula for Adonis tests for each PERMANOVA subset (yml file path).
    :param p_longi_column: If data is longitudinal; provide the time metadata column for volatility analysis.
    :param p_filt_threshs:
    :param force: Force the re-writing of scripts for all commands.
    :param i_classifier: Path to the taxonomic classifier.
    :param i_wol_tree: default to ./routine_qiime2_analyses/resources/wol_tree.nwk.
    :param i_sepp_tree: path to the SEPP database artefact. Default to None.
    :param i_qemistree: path to the tree generated using Qemistree (for metabolomics datasets).
    :param p_diff_models: Formulas for multinomial regression-based differential abundance ranking.
    :param p_mmvec_pairs: Pairs of datasets for which to compute co-occurrences probabilities.
    :param chmod: whether to change permission of output files (defalt: 775).
    :param p_skip: steps to skip.
    :param gpu: Use GPUs instead of CPUs for MMVEC.
    :param standalone:
    :param raref: Whether to only perform the routine analyses on the rarefied datasets.
    """

    # INITIALIZATION ------------------------------------------------------------
    # check input
    if not exists(i_datasets_folder):
        print('%s is not an existing folder\nExiting...' % i_datasets_folder)
        sys.exit(1)

    i_datasets_folder = abspath(i_datasets_folder)
    if isfile(i_datasets_folder):
        print('%s is a file. Needs a folder as input\nExiting...' % i_datasets_folder)
        sys.exit(1)

    # check Xpbs
    ret_code, ret_path = subprocess.getstatusoutput('which Xpbs')
    if ret_code:
        print('Xpbs is not installed (and make sure to edit its config.txt)\nExiting...')
        sys.exit(1)
    else:
        with open(ret_path) as f:
            for line in f:
                break
        if line.startswith('$HOME'):
            print('Xpbs is installed but its config.txt need editing!\nExiting...')
            sys.exit(1)

    prjct_nm = get_prjct_nm(project_name)
    run_params = get_run_params(p_run_params)

    # READ ------------------------------------------------------------
    print('(get_datasets)')
    datasets, datasets_read, datasets_features, datasets_phylo, datasets_rarefs = get_datasets(
        i_datasets, i_datasets_folder)

    filt_raref = ''
    if p_filt_threshs:
        filt_raref += '_flt'
    if raref:
        filt_raref += '_rrf'

    if eval_rarefs and not p_procrustes:
        p_procrustes = 1

    # PREPROCESSING ------------------------------------------------------------
    print('(import_datasets)')
    import_datasets(i_datasets_folder, datasets, datasets_phylo,
                    force, prjct_nm, qiime_env, chmod, noloc,
                    run_params['import'], filt_raref, jobs, chunkit)

    datasets_filt = {}
    datasets_filt_map = {}
    if p_filt_threshs:
        print('(filter_rare_samples)')
        filter_rare_samples(i_datasets_folder, datasets, datasets_read, datasets_features,
                            datasets_rarefs, datasets_filt, datasets_filt_map, datasets_phylo,
                            prjct_nm, qiime_env, p_filt_threshs, chmod, noloc,
                            run_params['filter'], filt_raref, jobs, chunkit)

    eval_depths = {}
    if raref:
        print('(run_rarefy)')
        eval_depths = run_rarefy(
            i_datasets_folder, datasets, datasets_read, datasets_phylo,
            datasets_filt_map, datasets_rarefs, p_raref_depths, eval_rarefs, force,
            prjct_nm, qiime_env, chmod, noloc, run_params['rarefy'],
            filt_raref, filt_only, jobs, chunkit)

    # TAXONOMY ------------------------------------------------------------
    taxonomies = {}
    method = 'sklearn'
    # method = 'hybrid-vsearch-sklearn'
    # method = 'consensus-blast'
    # method = 'consensus-vsearch'
    print('(get_precomputed_taxonomies)')
    get_precomputed_taxonomies(i_datasets_folder, datasets,
                               datasets_filt_map, taxonomies,
                               method)
    if i_qemistree and 'qemistree' not in p_skip:
        if isdir(i_qemistree):
            print('(run_qemistree)')
            run_qemistree(i_datasets_folder, datasets, prjct_nm,
                          i_qemistree, taxonomies, force, qiime_env,
                          chmod, noloc, run_params['qemistree'],
                          filt_raref, jobs, chunkit)
        else:
            print('[Warning] The Qemistree path %s is not a folder.')

    if 'taxonomy' not in p_skip:
        print('(run_taxonomy)')
        run_taxonomy(method, i_datasets_folder, datasets, datasets_read,
                     datasets_phylo, datasets_features, datasets_filt_map, i_classifier,
                     taxonomies, force, prjct_nm, qiime_env, chmod, noloc,
                     run_params['taxonomy'], filt_raref, jobs, chunkit)
        if 'barplot' not in p_skip:
            print('(run_barplot)')
            run_barplot(i_datasets_folder, datasets, taxonomies,
                        force, prjct_nm, qiime_env, chmod, noloc,
                        run_params['barplot'], filt_raref, jobs, chunkit)

        print('(run_edit_taxonomies)')
        edit_taxonomies(i_datasets_folder, taxonomies, force,
                        prjct_nm, qiime_env, chmod, noloc,
                        run_params['taxonomy'], filt_raref, jobs, chunkit)

    # TREES ------------------------------------------------------------
    trees = {}
    print('(get_precomputed_trees)')
    get_precomputed_trees(i_datasets_folder, datasets,
                          datasets_filt_map, datasets_phylo,
                          trees)
    if 'wol' not in p_skip:
        print('(shear_tree)')
        shear_tree(i_datasets_folder, datasets, datasets_read, datasets_phylo,
                   datasets_features, prjct_nm, i_wol_tree, trees, datasets_rarefs,
                   force, qiime_env, chmod, noloc, run_params['wol'], filt_raref, jobs)
    if i_sepp_tree and 'sepp' not in p_skip:
        print('(run_sepp)')
        run_sepp(i_datasets_folder, datasets, datasets_read, datasets_phylo,
                 datasets_rarefs, prjct_nm, i_sepp_tree, trees, force,
                 qiime_env, chmod, noloc, run_params['sepp'], filt_raref, jobs)

    if filt_only and datasets_filt_map:
        deleted_non_filt(datasets, datasets_read, datasets_features, datasets_phylo,
                         datasets_rarefs, taxonomies, datasets_filt, datasets_filt_map)

    split_taxa_pds = get_taxo_levels(taxonomies)
    if 'do_pies' in p_skip:
        print('(run_do_pies)')
        pies_data = make_pies(i_datasets_folder, split_taxa_pds,
                              datasets_rarefs, datasets_read)

    collapsed = {}
    datasets_collapsed = {}
    datasets_collapsed_map = {}
    if p_collapse_taxo and 'collapse' not in p_skip:
        print('(run_collapse)')
        collapsed = run_collapse(i_datasets_folder, datasets, datasets_filt, datasets_read,
                                 datasets_features, datasets_phylo, split_taxa_pds,
                                 taxonomies, p_collapse_taxo, datasets_rarefs,
                                 datasets_collapsed, datasets_collapsed_map, force,
                                 prjct_nm, qiime_env, chmod, noloc,
                                 run_params["collapse"], filt_raref, jobs)

    # datasets, datasets_read, datasets_feature, datasets_phylo, datasets_rarefs = clear_poor_datasets(
    #     datasets,
    #     datasets_read,
    #     datasets_features,
    #     datasets_phylo
    # )

    # ALPHA ------------------------------------------------------------
    if 'alpha' not in p_skip:
        print('(alpha)')
        diversities = run_alpha(i_datasets_folder, datasets, datasets_read,
                                datasets_phylo, datasets_rarefs, p_alpha_subsets,
                                trees, force, prjct_nm, qiime_env, chmod, noloc,
                                As, dropout, run_params['alpha'], filt_raref,
                                eval_depths, jobs, chunkit)
        if 'merge_alpha' not in p_skip:
            print('(to_export)')
            to_export = merge_meta_alpha(i_datasets_folder, datasets, datasets_rarefs,
                                         diversities, force, prjct_nm, qiime_env, chmod,
                                         noloc,  dropout, run_params['merge_alpha'],
                                         filt_raref, eval_depths, jobs, chunkit)
            if 'export_alpha' not in p_skip:
                print('(export_meta_alpha)')
                export_meta_alpha(datasets, filt_raref, datasets_rarefs, to_export, dropout)
        if 'alpha_correlations' not in p_skip:
            print('(run_correlations)')
            run_correlations(i_datasets_folder, datasets, diversities,
                             datasets_rarefs, force, prjct_nm, qiime_env,
                             chmod, noloc, run_params['alpha_correlations'],
                             filt_raref, jobs, chunkit)
        if p_longi_column:
            if 'volatility' not in p_skip:
                print('(run_volatility)')
                run_volatility(i_datasets_folder, datasets, p_longi_column,
                               datasets_rarefs, force, prjct_nm, qiime_env, chmod,
                               noloc, run_params['volatility'], filt_raref, jobs, chunkit)

    # BETA ----------------------------------------------------------------------
    if 'beta' not in p_skip:
        print('(betas)')
        betas = run_beta(i_datasets_folder, datasets, datasets_phylo,
                         datasets_read, datasets_rarefs, p_beta_subsets,
                         p_beta_groups, trees, force, prjct_nm, qiime_env,
                         chmod, noloc, Bs, dropout, run_params['beta'],
                         filt_raref, eval_depths, jobs, chunkit)
        if 'export_beta' not in p_skip:
            print('(export_beta)')
            export_beta(i_datasets_folder, betas, datasets_rarefs,
                        force, prjct_nm, qiime_env, chmod, noloc,
                        run_params['export_beta'], filt_raref, jobs, chunkit)
        if 'pcoa' not in p_skip:
            print('(run_pcoas)')
            pcoas = run_pcoas(i_datasets_folder, betas, datasets_rarefs,
                              force, prjct_nm, qiime_env, chmod, noloc,
                              run_params['pcoa'], filt_raref, jobs, chunkit)
            if 'emperor' not in p_skip:
                print('(run_emperor)')
                run_emperor(i_datasets_folder, pcoas, datasets_rarefs,
                            prjct_nm, qiime_env, chmod, noloc,
                            run_params['emperor'], filt_raref, jobs, chunkit)
            if 'empress' not in p_skip:
                print('(run_empress)')
                run_empress(i_datasets_folder, pcoas, trees, datasets_phylo,
                            datasets_rarefs, taxonomies, prjct_nm, qiime_env, chmod,
                            noloc, run_params['empress'], filt_raref, jobs, chunkit)
        if 'biplot' not in p_skip:
            print('(run_biplots)')
            biplots, biplots_raw = run_biplots(i_datasets_folder, betas,
                                               datasets_rarefs,  taxonomies,
                                               force, prjct_nm, qiime_env, chmod, noloc,
                                               run_params['biplot'], filt_raref, jobs, chunkit)
            if 'emperor_biplot' not in p_skip:
                print('(run_emperor_biplot)')
                run_emperor_biplot(i_datasets_folder, biplots, biplots_raw, taxonomies,
                                   split_taxa_pds, datasets_rarefs, prjct_nm, qiime_env, chmod,
                                   noloc, run_params['emperor_biplot'], filt_raref, jobs, chunkit)
            if 'empress_biplot' not in p_skip:
                print('(run_empress_biplot)')
                run_empress_biplot(i_datasets_folder, biplots, biplots_raw, trees, datasets_phylo,
                                   taxonomies, datasets_rarefs, prjct_nm, qiime_env, chmod,
                                   noloc, run_params['empress_biplot'], filt_raref, jobs, chunkit)

    # STATS ------------------------------------------------------------------
    if 'alpha' not in p_skip and 'alpha_group_significance' not in p_skip and 'alpha_kw' not in p_skip:
        print('(run_alpha_group_significance)')
        run_alpha_group_significance(i_datasets_folder, datasets, diversities,
                                     datasets_rarefs, p_beta_groups, force,
                                     prjct_nm, qiime_env, chmod, noloc, As, split,
                                     run_params['alpha_kw'], filt_raref, jobs, chunkit)

    if 'beta' not in p_skip and 'deicode' not in p_skip:
        print('(run_deicode)')
        run_deicode(i_datasets_folder, datasets, datasets_rarefs,
                    p_beta_groups, force, prjct_nm, qiime_env, chmod,
                    noloc, run_params['deicode'], filt_raref, jobs, chunkit)

    if 'beta' not in p_skip and p_perm_tests and 'permanova' not in p_skip:
        print('(run_permanova)')
        permanovas = run_permanova(i_datasets_folder, betas, p_perm_tests,
                                   p_beta_type, datasets_rarefs, p_beta_groups,
                                   force, prjct_nm, qiime_env, chmod, noloc, split,
                                   run_params['permanova'], filt_raref, jobs, chunkit)

        summarize_permanova(i_datasets_folder, permanovas,
                            prjct_nm, qiime_env, chmod, noloc, split,
                            run_params['permanova'], filt_raref,
                            jobs, chunkit)

    if 'beta' not in p_skip and p_formulas and 'adonis' not in p_skip:
        print('(run_adonis)')
        run_adonis(p_formulas, i_datasets_folder, betas, datasets_rarefs,
                   p_beta_groups, force, prjct_nm, qiime_env, chmod,
                   noloc, split, run_params['adonis'], filt_raref, jobs, chunkit)

    if 'beta' not in p_skip and p_procrustes and 'procrustes' not in p_skip:
        print('(run_procrustes)')
        run_procrustes(i_datasets_folder, datasets_filt, p_procrustes, betas,
                       force, prjct_nm, qiime_env, chmod, noloc, split,
                       run_params['procrustes'], filt_raref,
                       filt_only, eval_depths, jobs, chunkit)

    if 'beta' not in p_skip and p_mantel and 'mantel' not in p_skip:
        print('(run_mantel)')
        run_mantel(i_datasets_folder, datasets_filt, p_mantel, betas,
                   force,  prjct_nm, qiime_env, chmod, noloc, split,
                   run_params['mantel'], filt_raref,  filt_only, eval_depths, jobs, chunkit)

    if 'beta' not in p_skip and p_nestedness_groups and 'nestedness' not in p_skip:
        print('(run_nestedness)')
        nestedness_res, colors, nodfs_fps = run_nestedness(
            i_datasets_folder, betas, datasets_collapsed_map, p_nestedness_groups,
            datasets_rarefs, force, prjct_nm, qiime_env, chmod, noloc, split,
            run_params['nestedness'], filt_raref, jobs, chunkit)

        if nestedness_res:
            print('(making_nestedness_figures (graphs))')
            nestedness_graphs(i_datasets_folder, nestedness_res, datasets,
                                          split_taxa_pds, datasets_rarefs, colors,
                                          datasets_collapsed_map, collapsed, filt_raref,
                                          prjct_nm, qiime_env, chmod, noloc, split,
                                          run_params['nestedness'], jobs, chunkit)
        if nodfs_fps:
            print('(making_nestedness_figures (nodfs))')
            nestedness_nodfs(i_datasets_folder, nodfs_fps, collapsed,
                             filt_raref, prjct_nm, qiime_env, chmod,
                             noloc, split, run_params['nestedness'],
                             jobs, chunkit)

    if 'beta' not in p_skip and p_distance_decay and 'decay' not in p_skip:
        print('(run_distance_decay)')
        distance_decay_res = run_distance_decay(i_datasets_folder, betas, p_distance_decay,
                                                datasets_rarefs, force, prjct_nm, qiime_env,
                                                chmod, noloc, split, run_params['decay'],
                                                filt_raref, jobs, chunkit)
        if distance_decay_res:
            print('(making_distance_decay_figures)')
            distance_decay_figure(i_datasets_folder, distance_decay_res,
                                  datasets_rarefs, filt_raref)

    # PHATE ---------------------------------------------------------------------
    if p_phate_config and 'phate' not in p_skip:
            print('(run_phate)')
            phates = run_phate(
                p_phate_config, i_datasets_folder, datasets, datasets_rarefs,
                force, prjct_nm, qiime_env, chmod, noloc, split,
                run_params['phate'], filt_raref, jobs, chunkit)
    else:
        phates = {}

    # DISSIMILARITY OVERLAP --------------------------------------------
    if 'doc' not in p_skip and p_doc_config:
        print('(run_doc)')
        run_doc(i_datasets_folder, datasets, p_doc_config,
                datasets_rarefs, force, prjct_nm, qiime_env, chmod, noloc,
                run_params['doc'], filt_raref, phates, doc_phate, split, jobs, chunkit)

    # SOURCETRACKING --------------------------------------------
    if p_sourcetracking_config and 'sourcetracking' not in p_skip:
        print('(run_sourcetracking)')
        run_sourcetracking(i_datasets_folder, datasets, p_sourcetracking_config,
                           datasets_rarefs, force, prjct_nm, qiime_env, chmod,
                           noloc, run_params['sourcetracking'],
                           filt_raref, split, jobs, chunkit)

    # MMVEC AND SONGBIRD --------------------------------------------------------
    filts = {}
    input_to_filtered = {}
    mmvec_outputs = []
    if p_mmvec_pairs:
        if filt3d:
            filts.update(get_filt3d_params(p_mmvec_pairs, 'mmvec'))
        elif 'mmvec' not in p_skip:
            print('(run_mmvec)')
            mmvec_outputs = run_mmvec(p_mmvec_pairs, i_datasets_folder, datasets,
                                      datasets_filt, datasets_read, force, gpu,
                                      standalone, prjct_nm, qiime_env, chmod,
                                      noloc, split, filt_raref, run_params['mmvec'],
                                      input_to_filtered, jobs, chunkit)

    songbird_outputs = []
    if p_diff_models:
        if filt3d:
            filts.update(get_filt3d_params(p_diff_models, 'songbird'))
        elif 'songbird' not in p_skip:
            print('(run_songbird)')
            songbird_outputs = run_songbird(p_diff_models, i_datasets_folder,
                                            datasets, datasets_read, datasets_filt,
                                            input_to_filtered, mmvec_outputs, force, prjct_nm,
                                            qiime_env, chmod, noloc, split,
                                            run_params['songbird'], filt_raref, jobs, chunkit)
            q2s_pd = summarize_songbirds(i_datasets_folder)
            out_folder = get_analysis_folder(i_datasets_folder, 'songbird')
            q2s_fp = '%s/songbird_q2.tsv' % out_folder
            q2s_pd.to_csv(q2s_fp, index=False, sep='\t')
            print('\t\t==> Written:', q2s_fp)
            create_songbird_feature_metadata(i_datasets_folder, taxonomies, q2s_pd)

    if filt3d:
        print('(run_filt3d)')
        explore_filtering(i_datasets_folder, datasets, datasets_read,
                          datasets_filt, datasets_filt_map,
                          filts, p_filt3d_config)
    elif p_mmvec_pairs and 'mmbird' not in p_skip:
        print('(run_mmbird)')
        run_mmbird(
            i_datasets_folder, songbird_outputs, p_mmvec_highlights,
            p_xmmvec, mmvec_outputs, force, prjct_nm, qiime_env, chmod,
            noloc, filt_raref, run_params['mmbird'],
            input_to_filtered, jobs, chunkit)
