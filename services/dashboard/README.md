# trueview_api
Make sure all commands are run in dashboard folder

## deploy test
flyctl deploy --config fly.test.toml --dockerfile Dockerfile.test -a tv-mvp-test

(if you need to launch new app)
flyctl launch --config fly.test.toml --dockerfile Dockerfile.test

need to set secrets?
flystl set secrets <SECRETS_NAME>=<VALUE> -a tv-mvp-test

# prod
flyctl deploy

(if you need to launch new app)
flyctl launch

need to set secrets?
flystl set secrets <SECRETS_NAME>=<VALUE>