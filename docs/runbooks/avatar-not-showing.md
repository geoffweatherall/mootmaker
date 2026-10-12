# Avatar not showing

A person shows initials where a photo should be, or an old photo. How avatars work is in
[data](../overview/data.md#avatars).

Both apps show initials both for a person with no avatar and for one whose image failed to load, so
the first question is which it is.

```bash
# Ask the API for the person's avatar URL (with a signed-in user's token)
curl -s "$API" -H "Authorization: $TOKEN" -H 'content-type: application/json' \
  -d '{"query":"{ workspace { people { name avatarUrl } } }"}' | jq '.data.workspace.people[] | select(.name=="Ada Lovelace")'
curl -s -o /dev/null -w '%{http_code}\n' "<the avatarUrl>"
```

| Finding | Cause | Fix |
|---|---|---|
| `avatarUrl` is null | The person has no avatar. Real sign-ups have none unless one was uploaded; demo-data gives one to nine people in ten | Expected. Neither app has an upload screen yet; avatars are set through the API |
| URL returns 200, app shows initials | The client failed to load it: offline, or blocked by a network filter | Retry on another network |
| URL returns 403 or 404 | The object is missing from the avatars bucket, for example deleted by hand or by a reset that kept the Person | Upload again through the API, or run demo-data, which re-uploads for its people |
| DNS or TLS error on `avatars.<env>.mootmaker.com` | The avatars CloudFront distribution or its record | As for the site, in [site is down](site-is-down.md#1-the-site) |
| An old photo after a change | A cached copy: each image's URL is cached for a year, but a *new* image has a new URL. An old photo means the client still holds the old Person data | Reload; see [changes not showing](changes-not-showing.md) (people changes are not broadcast) |
| A deleted person's photo still loads by its URL | Edge caches keep it for a while after the object is deleted | Accepted. An invalidation can remove it at once: `aws cloudfront create-invalidation --distribution-id <avatars distribution> --paths '/v1/<personId>/*'` |

An upload that is refused says why (`NotAnImage`, `ImageTooSmall` below 64 pixels, `ImageTooLarge` above
4096, `UploadTooLarge` over 2 MiB, or a content type other than JPEG or PNG).
