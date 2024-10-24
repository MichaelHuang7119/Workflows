#!/usr/bin/python3
import tomllib, os, pathlib, subprocess

REPO_URL = "https://hf-mirror.com/{repo}/resolve/main/{src}?download=true"
PM_CACHE_DIR = os.environ.get("PM_CACHE_DIR", "/home/share/pm_cache")


def download(url: str, cache: str):
    print("download", cache, "from", url)
    pathlib.Path(cache).parent.mkdir(exist_ok=True, parents=True)
    if url.endswith(".git"):
        try:
            subprocess.run(["git", "clone", url, cache], check=True)
            print(f"Repository cloned to {cache}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone repository: {e}")
    else:
        if os.system("which aria2c"):
            if os.system(f"wget -c {url} -O {cache + '.tmp'}"):
                raise Exception("download failed")
        else:
            if os.system(f"aria2c -d / -c -j 10 -x 10 {url} -o {cache + '.tmp'}"):
                raise Exception("download failed")
        os.rename(cache + ".tmp", cache)


def symlink(cache: str, target: str):
    print("link", target, "from", cache)
    pathlib.Path(target).parent.mkdir(exist_ok=True, parents=True)
    os.symlink(cache, target)


def url_to_cache(url: str):
    url = url.removeprefix("https://").removeprefix("http://")
    assert "http" not in url
    return url


def local_path(path: str):
    if path.startswith("$PM_CACHE_DIR"):
        path = PM_CACHE_DIR + path.removeprefix("$PM_CACHE_DIR")
    return os.path.abspath(path)


def load_files_and_symlink(files, links, make_cache, make_target):
    for file in files:
        if isinstance(file, str):
            src = file
            dests = [file]
        else:
            src, dests = file["src"], file["dest"]
            dests = dests if isinstance(dests, list) else [dests]
        cache = make_cache(src)
        if not os.path.exists(cache):
            if make_url:
                url = make_url(src)
                download(url, cache)
            else:
                raise Exception("local file not found", cache)
        for dest in dests:
            target = make_target(dest)
            links.append((cache, target))
    return links


if __name__ == "__main__":
    with open("prepare_models.toml", "rb") as f:
        data = tomllib.load(f)
    links = []
    for source in data["sources"]:
        if "repo" in source:
            make_url = lambda src: REPO_URL.format(repo=source["repo"], src=src)
            make_cache = lambda src: os.path.join(PM_CACHE_DIR, source["repo"], src)
        elif "url" in source:
            make_url = lambda src: os.path.join(source["url"], src)
            make_cache = lambda src: os.path.join(
                PM_CACHE_DIR, url_to_cache(source["url"]), src
            )
        elif "local" in source:
            make_url = None
            make_cache = lambda src: os.path.join(local_path(source["local"]), src)
        else:
            raise NotImplementedError(source)
        make_target = lambda dest: os.path.join(
            os.getcwd(), source.get("path", ""), dest
        )

        load_files_and_symlink(source["files"], links, make_cache, make_target)

    for cache, target in links:
        if os.path.exists(target) and not os.path.islink(target):
            raise Exception("target exists, and is not symlink", target)
        if os.path.islink(target):
            if os.readlink(target) == cache:
                print("found", target)
                continue
            os.unlink(target)
        symlink(cache, target)
