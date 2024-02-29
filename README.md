# suggest

Suggest enables dynamic text-based filtering of spreadsheets in the browser. This repo is a stub implementation of the functionality, it can be forked and customized for your specific data needs.

This is nothing innovative, but what may be useful is the fact that the entire project is able to be hosted on Github pages, meaning there's no need to figure out where to host pages, run an API to handle the data or searching, etc.

The hosting pattern assumes users are okay posting the underlying data online in Github (you're searching it over a browser, so hopefully this isn't a problem, but you should be aware that nothing is hidden in this setup).

Ideally, there won't be much new coding to do for downstream users, but there are some setup steps that you'll need to do as detailed in the next section.

## Usage

1. Fork this repo.
2. Clone the repo on your machine and go into the base directory.
3. Create an environment.
4. Getting hostable data (option a):
    4. Install the package
    2. Change the `./data/raw.csv` to your own source.
    3. Change `./config.yaml` to set the `used_fields` from the csv. These are the subset of fields you want filter and the field names are case sensitive.
    4. Run `format_data.py`.
4. Getting hostable data (option b):

4. Commit `./config.yaml`, `./data/clean.csv`, and any other changed files to your repo.
5. Update `./docs/python/pyscript.json` to have the files point to the `raw` github locations of those files.
6. Commit `./docs/python/pyscript.json`
7. Create a github page for your repo
    1. Go to your repo settings
    2. Go to pages
    3. Add pages on main branch
8. Navigate to the pages to see the results

### Local development

Pushing changes to Github and waiting for pages to load can be time consuming, so I would recommend iterating locally whenever possible. To view your website locally, enter the base directory of the project and on the terminal type:
```bash
python -m http.server
```
Then open `http://localhost:8000/docs/index.html` in your browser. Any changes you make to the website should be reflected in the page after refreshing. When you're happy with the results, commit your changes to Github to have the hosted version of the page match your local version.

If you don't do much web development, get familiar with Chrome's right-click -> Inspect option. You can test out changes to css without reloading the page, which can save time when making changes.