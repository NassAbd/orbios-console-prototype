#include "payload.h"

#define THRESHOLD_BRIGHTNESS 330.0
#define THRESHOLD_FRP_HIGH   50.0

float compute_risk_score(SensorData data) {

    float conf_score;

    // confidence logic
    switch(data.confidence) {

        case 'h':
            conf_score = 1.0;
            break;

        case 'n':
            conf_score = 0.6;
            break;

        case 'l':
            conf_score = 0.3;
            break;

        default:
            conf_score = 0.3;
    }

    // normalize FRP
    float frp_norm = data.frp / THRESHOLD_FRP_HIGH;

    if(frp_norm > 1.0)
        frp_norm = 1.0;

    // thermal anomaly
    float thermal_flag = 0;

    if(data.brightness > THRESHOLD_BRIGHTNESS)
        thermal_flag = 1.0;

    // weighted wildfire probability
    float probability =
        (0.40 * conf_score) +
        (0.35 * frp_norm) +
        (0.25 * thermal_flag);

    return probability;
}

int generate_alert(SensorData data, float score) {

    // realistic wildfire detection
    if(score >= 0.55)
        return 1;

    return 0;
}