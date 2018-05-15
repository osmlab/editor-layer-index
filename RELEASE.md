## Release Checklist

### Update master branch
- [ ] git checkout master
- [ ] npm install
- [ ] npm run test
- [ ] npm run txpull
- [ ] git add . && git commit -m 'npm run txpull'
- [ ] Update `CHANGELOG.md`
- [ ] Update version number in `package.json`
- [ ] git add . && git commit -m 'vA.B.C'
- [ ] git push origin master

### Update release branch, tag and publish
- [ ] git checkout release
- [ ] git reset --hard master
- [ ] npm run build
- [ ] git add -f dist/*
- [ ] git commit -m 'Check in build'
- [ ] git tag vA.B.C
- [ ] git push origin -f release vA.B.C
- [ ] npm publish

Open https://github.com/osmlab/editor-layer-index/tags
Click "Add Release Notes" and link to the CHANGELOG
