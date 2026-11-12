# MusiCoMMA: Musiconis vocabulary and context-reviewed CoMMA pilot

Research software accompanying the [v0.2.1 dataset by Xavier Fresquet and Frédéric Billiet](https://doi.org/10.5281/zenodo.22724676). The five Python scripts and the analysis notebook come from the archived release. Manuscript images, source shards and editorial files are not distributed here. Download the dataset and precomputed exposure cache from Zenodo.

## Verify the release

Extract the ZIP from [Zenodo](https://zenodo.org/records/22724676). In a Python environment, run from this repository:

~~~sh
python -m pip install rdflib==7.1.4
MUSICOMMA_DATA_ROOT=/absolute/path/to/musiconis-comma-v0.2.1-zenodo python -m unittest discover -s scripts
~~~

The six checks cover the released data and checksums. For notebook analysis, use Python 3.12 and the archived `requirements-analysis.txt`; run the notebook in a working copy of the extracted archive. Counts describe the reviewed pilot, not the prevalence of musical terminology in all medieval manuscripts.

## Citation and provenance

- [MusiCoMMA v0.2.1, Zenodo](https://doi.org/10.5281/zenodo.22724676) · [all versions](https://doi.org/10.5281/zenodo.22724675).
- Upstream HTR corpus: Clérice et al., [CoMMA, a Large-scale Corpus of Multilingual Medieval Archives, HAL](https://hal.science/hal-05299220v2). The HAL paper describes CoMMA, not this derived dataset.
- Vocabulary source: Musiconis, Sorbonne Université. Retain both source credits when reusing the data.

Code and notebooks: [MIT](LICENSE-CODE). Data and source notices: see the Zenodo release.
