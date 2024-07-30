FROM python:3.10-alpine as base

RUN apk --no-cache add tzdata && pip install --no-cache-dir --no-warn-script-location hetzner-snap-and-rotate

# Produce a squashed image
FROM scratch

COPY --from=base / /

ENV USER=hetzner

# Prevent $0 in ENTRYPOINT to resolve to /bin/sh if the container is run without any command line options
CMD [""]

ENTRYPOINT python -m hetzner_snap_and_rotate $0 $@
