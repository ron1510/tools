{{- define "gremlin-arangodb-poc.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "gremlin-arangodb-poc.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- default .Release.Name (include "gremlin-arangodb-poc.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "gremlin-arangodb-poc.secretName" -}}
{{- if .Values.arangodb.auth.existingSecret -}}
{{- .Values.arangodb.auth.existingSecret -}}
{{- else -}}
{{- printf "%s-arangodb" (include "gremlin-arangodb-poc.fullname" .) -}}
{{- end -}}
{{- end -}}
