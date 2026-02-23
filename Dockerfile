# Stage 1: Build
FROM golang:1.26.0-alpine AS builder
RUN apk add --no-cache git make
WORKDIR /src
RUN git clone https://github.com/sipeed/picoclaw.git .
RUN go mod download
RUN make build

# Stage 2: Runtime (HF Spaces requires UID 1000)
FROM alpine:3.23
RUN apk add --no-cache ca-certificates tzdata
RUN adduser -D -u 1000 user
USER user
WORKDIR /home/user/app

COPY --from=builder /src/build/picoclaw .
COPY --chown=user:user config.json .
COPY --chown=user:user entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 7860
CMD ["./entrypoint.sh"]
