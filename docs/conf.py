"""Sphinx configuration for orpen-sc-pdk documentation."""

project = "orpen-sc-pdk"
author = "I-Li Chiu"
copyright = "I-Li Chiu"  # noqa: A001
root_doc = "index"

extensions = [
    "myst_nb",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.imgconverter",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx_github_alerts",
    "sphinxcontrib.bibtex",
    "sphinxcontrib.mermaid",
    "sphinxcontrib.svgbob",
    "sphinxcontrib_bibtex_urn",
]

exclude_patterns = [
    "_build",
    "conf.py",
    "Thumbs.db",
    ".DS_Store",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "gdsfactory": ("https://gdsfactory.github.io/gdsfactory/", None),
}

myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3
myst_url_schemes = ("http", "https", "mailto")

nb_execution_mode = "cache"
nb_execution_timeout = -1
nb_execution_allow_errors = False
nb_execution_raise_on_error = True
nb_execution_excludepatterns = [
    "notebooks/public_*_workflow.ipynb",
    "notebooks/SGB_Geometry_Tutorials/*.ipynb",
]
nb_custom_formats = {
    ".py": ["jupytext.reads", {"fmt": "py:percent"}],
}

autodoc_typehints = "description"
autodoc_typehints_format = "short"
napoleon_google_docstring = True
autosectionlabel_prefix_document = True
autosummary_generate = True

bibtex_bibfiles = ["references.bib"]

html_theme = "pydata_sphinx_theme"
html_show_copyright = False
html_title = "orpen-sc-pdk"
html_theme_options = {
    "github_url": "https://github.com/OrPenStrike/orpen-sc-pdk",
    "navigation_with_keys": True,
    "show_toc_level": 2,
    "use_edit_page_button": True,
}
html_context = {
    "github_user": "OrPenStrike",
    "github_repo": "orpen-sc-pdk",
    "github_version": "main",
    "doc_path": "docs",
}
html_static_path = []

latex_engine = "xelatex"
latex_use_xindy = False
latex_documents = [
    (
        root_doc,
        "orpen-sc-pdk.tex",
        "orpen-sc-pdk Documentation",
        author,
        "manual",
    )
]
latex_elements = {
    "papersize": "a4paper",
    "pointsize": "11pt",
    "preamble": r"""
\setcounter{tocdepth}{2}
\setlength{\headheight}{14pt}
""",
}
