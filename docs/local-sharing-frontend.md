# Local Sharing frontend integration

`static/local-sharing.js` supplies room navigation, create/join validation, room selection, multiple-file selection, file downloads, notes, search, removal, and leave controls.

The default adapter holds rooms and File objects in this tab's memory. Refresh clears them. It performs no LAN discovery, cross-device transfer, persistence, or network authentication.

To connect a backend, define `window.netdropLocalAdapter` before loading this script. All methods are asynchronous:

- `list()` returns rooms with `id` and `name` (do not return PINs from the backend).
- `create(name, pin)` and `join(id, pin)` return `{id, name}`.
- `items(roomId)` returns items with `id`, `name`, and optionally `size` and `url` for files.
- `add(roomId, item)` accepts `{name}` for notes or `{name, file, size}` for uploads. `file` is a browser File object.
- `remove(roomId, itemId)` deletes an item.
- `leave(roomId)` ends room access.

Throw an Error with a user-facing message for failures. The backend must enforce room membership, validate PINs, authorize downloads/removals, and supply discovered rooms. The frontend disables action buttons while operations are pending and renders names/notes as text.
