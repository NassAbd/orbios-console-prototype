#ifndef PAYLOAD_H
#define PAYLOAD_H

typedef struct {

    float lat;
    float lon;
    int time;

    float brightness;
    float frp;

    char confidence;

} SensorData;

float compute_risk_score(SensorData data);
int generate_alert(SensorData data, float score);

#endif