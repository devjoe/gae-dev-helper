# GAE Dev Helper

A lovely command-line helper for developing GAE applications.
  
Features:
* Colorize and filter you server log in terminal.
* Do syntax highlight when you debug in Pdb.
* Help you to connect to remote_api by Ipython or PtPython.
* Convenient commands to control dev server. 
  
Note:
* **Current release is a debug version. Use with caution.** 🔔
  
## Installation  
  
In your virtualenv, do:
```
pip install gaedevhelper
```

> If you want to use remote_api, it's recommanded to install `ipython` or `ptpython`, too.
> If you want to debug by Pdb, it's recommanded to install `rlwrap`. (mac: `brew install rlwrap`)

Then:

```
gaedh init
```

Finally, edit confikikikig.py and fill out it.
```
vim ~/.gae_dev_helper/config.py
```

## Screenshots

Combine with `rlwrap` cmd:
```
rlwrap gaedh run
```
![](https://dl.dropboxusercontent.com/u/7414946/github/1__rlwrap_gaedh_run__rlwrap_.png)

Connect to remote_api by PtPython:
```
gaedh remote_api --dev --shell ptpython
```
![](https://dl.dropboxusercontent.com/u/7414946/github/1__gaedh_remote_api_--dev_--shell_ptpython__python_.png)
  
  
## Usages

`--help` is your good friend! You can use:

```
gaedh --help
```
Or:
```
gaedh run --help
gaedh interactive --help
...
```

If your want to debug in Pdb, please use `rlwrap` to wrap `gaedh` to enable c-p c-n c-r ... :
```
rlwrap gaedh run
```


## TODO
* [ ] Debug
* [ ] Documentation
* [ ] Reorder Tests
* [ ] Support more dev_appserver.py options in config.py
* [ ] Support php/Go (?)

