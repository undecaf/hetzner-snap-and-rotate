FROM python:3.10-alpine

RUN apk --no-cache add tzdata && pip install --no-cache-dir --no-warn-script-location hetzner-snap-and-rotate

ENV USER=hetzner
CMD [""]
ENTRYPOINT python -m hetzner_snap_and_rotate $0 $@
