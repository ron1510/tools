# rest-cache-lab Helm Chart

Lab backend chart for exercising the Varnish REST cache chart.

```powershell
helm upgrade --install rest-cache-lab ./charts/rest-cache-lab
helm upgrade --install rest-cache ./charts/rest-cache `
  --set varnish.backend.host=rest-cache-lab.default.svc.cluster.local
```
