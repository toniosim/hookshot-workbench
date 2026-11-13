"""Post a Longshot PR comment whose Markdown references local pictures as ![caption](IMG:file.png).

Posts the comment, uploads each picture as an attachment of that comment, then edits the comment so the IMG:
links point at the attachments. Usage: post_with_images.py <pr> <comment.md> <pictures dir> [--dry-run]
"""
import json, mimetypes, os, re, sys, urllib.parse, urllib.request, uuid

sys.path.insert(0, "/home/tonesi/Hookshot/scripts")
import forge  # noqa: E402
import magicbean_login as auth  # noqa: E402

IMG = re.compile(r"\(IMG:([^)\s]+)\)")


def upload(comment_id, path):
    name = os.path.basename(path)
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        data = f.read()
    body = (("--%s\r\nContent-Disposition: form-data; name=\"attachment\"; filename=\"%s\"\r\n"
             "Content-Type: %s\r\n\r\n" % (boundary, name, ctype)).encode() + data
            + ("\r\n--%s--\r\n" % boundary).encode())
    url = "%s/api/v1/repos/%s/issues/comments/%d/assets?name=%s" % (forge.BASE, forge.REPO, comment_id,
                                                                     urllib.parse.quote(name))
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "User-Agent": auth.USER_AGENT, "Accept": "application/json",
        "Authorization": "Bearer " + forge.token()["access_token"],
        "Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["browser_download_url"]


def main():
    pr, md, pics = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    dry = "--dry-run" in sys.argv
    text = open(md, encoding="utf-8").read()
    names = list(dict.fromkeys(IMG.findall(text)))
    missing = [n for n in names if not os.path.isfile(os.path.join(pics, n))]
    if missing:
        sys.exit("missing pictures: %s" % ", ".join(missing))
    print("pictures:", ", ".join(names) or "none")
    if dry:
        print(IMG.sub("(attachment)", text))
        return
    first = IMG.sub("(picture uploading)", text)
    c = forge.api("POST", "/repos/%s/issues/%d/comments" % (forge.REPO, pr), {"body": first})
    cid, html = c["id"], c["html_url"]
    print("posted", html)
    links = {}
    for n in names:
        links[n] = upload(cid, os.path.join(pics, n))
        print("uploaded", n, links[n])
    final = IMG.sub(lambda m: "(%s)" % links[m.group(1)], text)
    forge.api("PATCH", "/repos/%s/issues/comments/%d" % (forge.REPO, cid), {"body": final})
    print("edited", html)


if __name__ == "__main__":
    main()
