## 1. Setup

- [ ] 1.1 Create `scripts/` directory if not exists
- [ ] 1.2 Add `exports/` to `.gitignore`

## 2. Build Script Implementation

- [ ] 2.1 Create `scripts/build-production.sh` with basic structure
- [ ] 2.2 Implement Dockerfile existence check
- [ ] 2.3 Implement Docker availability check
- [ ] 2.4 Implement version information output (git commit, timestamp)
- [ ] 2.5 Define image build list (frontend, backend, gateway, workspace - excluding authentik)
- [ ] 2.6 Implement proxy environment variable passing (--build-arg for HTTP_PROXY, HTTPS_PROXY, NO_PROXY)
- [ ] 2.7 Implement `--incremental` flag to skip existing images
- [ ] 2.8 Implement `--force` flag to rebuild all images
- [ ] 2.9 Implement sequential build with progress output
- [ ] 2.10 Implement build summary report

## 3. Export Script Implementation

- [ ] 3.1 Create `scripts/export-images.sh` with basic structure
- [ ] 3.2 Implement `exports/` directory creation
- [ ] 3.3 Implement image existence check before export
- [ ] 3.4 Implement `docker save` for each image to tar file
- [ ] 3.5 Implement file size reporting in summary
- [ ] 3.6 Implement error handling for missing images

## 4. Verification

- [ ] 4.1 Test full build: run build script and verify all images created
- [ ] 4.2 Test incremental build: verify existing images are skipped
- [ ] 4.3 Test force rebuild: verify all images are rebuilt
- [ ] 4.4 Test proxy configuration: verify proxy args passed to docker build
- [ ] 4.5 Test export: verify tar files created in exports/ directory
- [ ] 4.6 Verify .gitignore excludes exports/ directory