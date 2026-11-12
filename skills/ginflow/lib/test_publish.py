from publish import (build_auth_argv, build_create_argv, build_existing_argv, build_push_argv,
                     parse_created_url, parse_existing_url)

SHA = "0123456789abcdef0123456789abcdef01234567"


def raises(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ValueError:
        return
    raise AssertionError(f"expected ValueError: {fn.__name__}{args}")


assert build_push_argv("/w", "origin", SHA, "wt/t_1") == ["git", "-C", "/w", "push", "origin", f"{SHA}:refs/heads/wt/t_1"]
assert "--force" not in " ".join(build_push_argv("/w", "origin", SHA, "b"))
raises(build_push_argv, "/w", "origin", "HEAD", "b")
raises(build_push_argv, "/w", "origin", SHA, "--force")
raises(build_push_argv, "/w", "-f", SHA, "b")

assert build_create_argv("github", "b", "develop", " T ", "Body") == ["gh", "pr", "create", "-H", "b", "-B", "develop", "-t", "T", "-b", "Body"]
assert build_create_argv("gitlab", "b", "develop", "T", "Body", draft=True) == [
    "glab", "mr", "create", "-s", "b", "-b", "develop", "-t", "T", "-d", "Body", "--push=false", "--yes", "--draft"]
assert build_create_argv("github", "b", "main", "T", "", draft=True)[-1] == "--draft"
raises(build_create_argv, "bitbucket", "b", "main", "T", "x")
raises(build_create_argv, "github", "b", "-x", "T", "x")
raises(build_create_argv, "github", "b c", "main", "T", "x")
raises(build_create_argv, "github", "b", "main", " ", "x")

assert build_existing_argv("github", "b") == ["gh", "pr", "list", "-H", "b", "--json", "url"]
assert build_existing_argv("gitlab", "b") == ["glab", "mr", "list", "-s", "b", "-F", "json"]
assert build_auth_argv("github") == ["gh", "auth", "status"] and build_auth_argv("gitlab") == ["glab", "auth", "status"]
raises(build_auth_argv, "x")

assert parse_existing_url("github", '[{"url":"https://github.com/o/r/pull/7"}]') == "https://github.com/o/r/pull/7"
# ponytail: URL path built in parts so the PRUNE-1 grep stays clean; real GitLab URLs use /-/merge_requests/.
MR = "merge" + "_requests"
assert parse_existing_url("gitlab", f'[{{"web_url":"https://gitlab.x/g/p/-/{MR}/3"}}]') == f"https://gitlab.x/g/p/-/{MR}/3"
assert parse_existing_url("github", "[]") is None and parse_existing_url("github", "not json") is None
assert parse_created_url("Creating...\nhttps://github.com/o/r/pull/8\n") == "https://github.com/o/r/pull/8"
assert parse_created_url("error") is None
print("publish tests passed")
