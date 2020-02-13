# ----------------------------------------------------------------------------
# Copyright (c) 2020, Franck Lejzerowicz.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import re
import sys
import pandas as pd
import pkg_resources
from os.path import basename, splitext, isfile, isdir

RESOURCES = pkg_resources.resource_filename("routine_qiime2_analyses", "resources")


def run_import(input_path: str, output_path: str, typ: str) -> str:
    """
    Return the import qiime2 command.

    :param input_path: input file path.
    :param output_path: output file path.
    :param typ: qiime2 type.
    :return: command to qiime2.
    """
    cmd = ''
    if typ.startswith("FeatureTable"):
        if not input_path.endswith('biom'):
            cur_biom = '%s.biom' % splitext(input_path)[0]
            cmd += 'biom convert \\ \n'
            cmd += '  -i %s \\ \n' % input_path
            cmd += '  -o %s \\ \n' % cur_biom
            cmd += '  --table-type="OTU table" \\ \n'
            cmd += '  --to-hdf5\n\n'
            cmd += 'qiime tools import \\ \n'
            cmd += '  --input-path %s \\ \n' % cur_biom
            cmd += '  --output-path %s \\ \n' % output_path
            cmd += '  --type "FeatureTable[Frequency]"\n'
        else:
            cmd += 'qiime tools import \\ \n'
            cmd += '  --input-path %s \\ \n' % input_path
            cmd += '  --output-path %s \\ \n' % output_path
            cmd += '  --type "FeatureTable[Frequency]"\n'
    else:
        cmd += 'qiime tools import \\ \n'
        cmd += '  --input-path %s \\ \n' % input_path
        cmd += '  --output-path %s \\ \n' % output_path
        cmd += '  --type "%s"\n' % typ
    return cmd


def run_export(input_path: str, output_path: str, typ: str) -> str:
    """
    Return the export qiime2 command.

    :param input_path: input file path.
    :param output_path: output file path.
    :param typ: qiime2 type.
    :return: command to qiime2.
    """
    cmd = ''
    if typ.startswith("FeatureTable"):
        if not output_path.endswith('biom'):
            cur_biom = '%s.biom' % splitext(output_path)[0]
            cmd += 'qiime tools export \\ \n'
            cmd += '  --input-path %s \\ \n' % input_path
            cmd += '  --output-path %s\n' % splitext(output_path)[0]
            cmd += 'mv %s/*.biom %s\n' % (splitext(output_path)[0], cur_biom)
            cmd += 'biom convert'
            cmd += '  -i %s \\ \n' % cur_biom
            cmd += '  -o %s.tmp \\ \n' % output_path
            cmd += '  --to-tsv\n\n'
            cmd += 'tail -n +2 %s.tmp > %s\n\n' % (output_path, output_path)
            cmd += 'rm -rf %s %s.tmp\n' % (splitext(output_path)[0], output_path)
        else:
            cmd += 'qiime tools export \\ \n'
            cmd += '  --input-path %s \\ \n' % input_path
            cmd += '  --output-path %s\n' % splitext(output_path)[0]
            cmd += 'mv %s/*.biom %s\n' % (splitext(input_path)[0], output_path)
            cmd += 'rm -rf %s\n' % splitext(input_path)[0]
    else:
        cmd += 'qiime tools export \\ \n'
        cmd += '  --input-path %s \\ \n' % input_path
        cmd += '  --output-path %s\n' % splitext(output_path)[0]
        if 'Phylogeny' in typ:
            cmd += 'mv %s/*.nwk %s\n' % (splitext(output_path)[0], output_path)
        else:
            cmd += 'mv %s/*.tsv %s\n' % (splitext(output_path)[0], output_path)
        cmd += 'rm -rf %s\n' % splitext(output_path)[0]
    return cmd


def get_corresponding_meta(path):
    """
    Automatically gets the metadata file corresponding to the tsv / biom file.

    :param path: Path of the tsv / biom file.
    :return:
    """
    meta_rad = splitext(path.replace('/data/', '/metadata/').replace('/tab_', '/meta_'))[0]
    meta_tsv = '%s.tsv' % meta_rad
    meta_txt = '%s.txt' % meta_rad
    if isfile(meta_tsv):
        return meta_tsv
    elif isfile(meta_txt):
        return meta_txt
    else:
        print('No metadata found for %s\n(was looking for:\n- %s\n- %s)' % (path, meta_tsv, meta_txt))
        sys.exit(1)


def get_paths(i_datasets: tuple, i_datasets_folder: str) -> dict:
    """

    :param i_datasets: Internal name identifying the datasets in the input folder.
    :param i_datasets_folder: Path to the folder containing the data/metadata subfolders.
    :return:
    """
    tsvs = []
    paths = {}
    for i_dataset in i_datasets:
        tsv = '%s/data/tab_%s.tsv' % (i_datasets_folder, i_dataset)
        biom = '%s.biom' % splitext(tsv)[0]
        tsvs.append(tsv)
        if isfile(tsv):
            paths[i_dataset] = tsv
        elif isfile(biom):
            paths[i_dataset] = biom
    if not paths:
        print('None of these target files found in input folder %s:' % i_datasets_folder)
        for tsv in tsvs:
            print(' - %s (or .biom)' % tsv)
        print('Exiting...')
        sys.exit(1)
    return paths


def gID_or_DNA(dat: str, path: str, path_pd: pd.DataFrame, datasets_read: dict,
               datasets_features: dict, datasets_phylo: dict) -> None:
    """
    Check whether the features of the current dataset are or contain:
    - genome IDs: then collect the gID -> corrected feature names for Web of Life tree shearing.
    - DNA sequences (e.g. typically deblur): then have a flag for sepp/phylo placement.
    (- to be developed for non-DNA OTU IDs associated with fasta sequences for sepp/phylo placement.)

    :param dat: name of the current dataset.
    :param path: feature table file path in the ./data folder.
    :param path_pd: feature table cotaining the features names in index.
    :param datasets_read: dataset -> [tsv table, meta table] (here it updates tsv table after features correction)
    :param datasets_features: to be updated with {gID: corrected feature name (no ';' or ' ')} per dataset.
    :param datasets_phylo: to be updated with ('tree_to_use', 'corrected_or_not') per dataset.
    """
    # regex to find the fist non-DNA character
    not_DNA = re.compile('[^ACGTN].*?')
    if str(path_pd.index.dtype) == 'object':
        features_names = path_pd.index.tolist()
        # check if that's genome IDs
        found_gids = {}
        DNA = True
        correction_needed = False
        for features_name in features_names:
            if DNA and bool(not_DNA.search(features_name)):
                DNA = False
            if re.search('G\d{9}', features_name):
                if ';' in features_name:
                    correction_needed = True
                    features_name_corr = features_name.replace(';', '|').replace(' ', '')
                else:
                    features_name_corr = features_name
                found_gids[re.search('G\d{9}', features_name).group(0)] = features_name_corr
        if len(found_gids) == len(features_names):
            datasets_features[dat] = found_gids
            if correction_needed:
                path_pd.index = path_pd.index.str.replace(r'[; ]+', '|')
                path_pd.reset_index().to_csv('%s.tmp' % path, index=False, sep='\t')
                datasets_read[dat][0] = path_pd
                datasets_phylo[dat] = ('wol', 1)
            else:
                datasets_phylo[dat] = ('wol', 0)
        elif DNA:
            datasets_phylo[dat] = ('amplicon', 0)


def get_datasets(i_datasets: tuple, i_datasets_folder: str) -> (dict, dict, dict, dict):
    """
    Collect the pairs of features tables / metadata tables, formatted as in qiime2. e.g:

        --> Feature table example:

        #Feature ID  BVC.1591.10.10  BVC.1509.10.36  BVC.1584.10.10
        G000006785              0.0             0.0           175.0
        G000006925          34614.0          5973.0         12375.0
        G000007265              0.0           903.0           619.0

        --> Metadata table example:

        SampleID        age_years  age_wk40
        BVC.1591.10.10       0.75      0.79
        BVC.1509.10.36       3.00      0.77
        BVC.1584.10.10       0.75      0.77

    :param i_datasets: Internal name identifying the datasets in the input folder.
    :param i_datasets_folder: Path to the folder containing the data/metadata subfolders.
    :return
    """
    print('# Fetching data and metadata (in %s)' % ', '.join(i_datasets))
    paths = get_paths(i_datasets, i_datasets_folder)

    datasets = {}
    datasets_read = {}
    datasets_phylo = {}
    datasets_features = {}
    for dat, path in paths.items():
        meta = get_corresponding_meta(path)
        if not isfile(meta):
            print(meta)
        path_pd = pd.read_csv(path, header=0, index_col=0, sep='\t')
        meta_pd = pd.read_csv(meta, header=0, sep='\t')
        datasets[dat] = [path, meta]
        datasets_read[dat] = [path_pd, meta_pd]
        datasets_features[dat] = {}
        datasets_phylo[dat] = ('', 0)
        gID_or_DNA(dat, path, path_pd, datasets_read, datasets_features, datasets_phylo)
    return datasets, datasets_read, datasets_features, datasets_phylo


def get_prjct_nm(project_name: str) -> str:
    """
    Get a smaller name for printing in qstat / squeue.

    :param project_name: Nick name for your project.
    :return: Shorter name (without vows).
    """
    alpha = 'aeiouy'
    prjct_nm = ''.join(x for x in project_name if x.lower() not in alpha)
    if prjct_nm == '':
        prjct_nm = 'q2.routine'
    return prjct_nm


def get_job_folder(i_datasets_folder: str, analysis: str):
    """
    Get the job folder name.

    :param i_datasets_folder: Path to the folder containing the data/metadata subfolders.
    :param analysis: name of the qiime2 analysis (e.g. beta)
    :return: job folder name
    """
    job_folder = '%s/jobs/%s' % (i_datasets_folder, analysis)
    if not isdir(job_folder):
        os.makedirs(job_folder)
    return job_folder


def get_analysis_folder(i_datasets_folder, analysis):
    """
    Get the output folder name.

    :param i_datasets_folder: Path to the folder containing the data/metadata subfolders.
    :param analysis: name of the qiime2 analysis (e.g. beta)
    :return: output folder name
    """
    odir = '%s/qiime/%s' % (i_datasets_folder, analysis)
    if not isdir(odir):
        os.makedirs(odir)
    return odir


def get_metrics(file_name: str) -> list:
    """
    Collect the alpha or beta diversity metrics from a resources file.

    :param file_name: name of the *_metrics file.
    :return: alpha or beta diversity metrics.
    """
    metrics = []
    with open('%s/%s.txt' % (RESOURCES, file_name)) as f:
        for line in f:
            line_strip = line.strip()
            if len(line_strip):
                metrics.append(line_strip)
    return metrics


def get_wol_tree(i_wol_tree: str) -> str:
    """
    :param i_wol_tree: passed path to a tree.
    :return: path to a verified tree .nwk file.
    """
    if i_wol_tree == 'resources/wol_tree.nwk':
        return '%s/wol_tree.nwk' % RESOURCES
    if not isfile(i_wol_tree):
        print('%s does not exist\nExiting...' % i_wol_tree)
        sys.exit(1)
    elif not i_wol_tree.endswith('nwk'):
        if i_wol_tree.endswith('qza'):
            i_wol_tree_nwk = '%s.nwk' % splitext(i_wol_tree)[0]
            if isfile(i_wol_tree_nwk):
                print('Warning: about to overwrite %s\nExiting' % i_wol_tree_nwk)
                sys.exit(1)
            run_export(i_wol_tree, i_wol_tree_nwk, 'Phylogeny')
            return i_wol_tree_nwk
        else:
            # need more formal checks (sniff in skbio / stdout in "qiime tools peek")
            print('%s is not a .nwk (tree) file or not a qiime2 Phylogeny artefact\nExiting...' % i_wol_tree)
            sys.exit(1)


def get_sepp_tree(i_sepp_tree: str) -> str:
    """
    Get the full path of the reference database for SEPP.

    :param i_sepp_tree: database to use.
    :return: path.
    """
    if not isfile(i_sepp_tree):
        print('%s does not exist\nExiting...' % i_sepp_tree)
        sys.exit(1)
    if not i_sepp_tree.endswith('qza'):
        print('%s is not a qiime2 Phylogeny artefact\nExiting...' % i_sepp_tree)
        sys.exit(1)
    if basename(i_sepp_tree) in ['sepp-refs-silva-128.qza',
                                 'sepp-refs-gg-13-8.qza']:
        return i_sepp_tree
    else:
        print('%s is not:\n- "sepp-refs-silva-128.qza"\n- "sepp-refs-gg-13-8.qza"\n'
              'Download: https://docs.qiime2.org/2019.10/data-resources/#sepp-reference-databases)\n'
              'Exiting...' % i_sepp_tree)
        sys.exit(1)
