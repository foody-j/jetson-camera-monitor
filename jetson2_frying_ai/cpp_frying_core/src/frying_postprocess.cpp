#include <algorithm>
#include <cmath>
#include <cstdint>

extern "C" int calc_frying_features(
    const uint8_t* hsv,
    const uint8_t* lab,
    const uint8_t* mask,
    int h,
    int w,
    double* out_vals
) {
    if (!hsv || !lab || !mask || !out_vals || h <= 0 || w <= 0) {
        return -1;
    }

    // out_vals layout:
    // 0: food_area_ratio
    // 1..3: mean_hsv
    // 4..6: std_hsv
    // 7..9: mean_lab
    // 10: dominant_hue
    // 11: saturation_mean
    // 12: value_mean
    // 13: brown_ratio
    // 14: golden_ratio
    for (int i = 0; i < 15; ++i) out_vals[i] = 0.0;

    const int total = h * w;
    double sum_h = 0.0, sum_s = 0.0, sum_v = 0.0;
    double sum_h2 = 0.0, sum_s2 = 0.0, sum_v2 = 0.0;
    double sum_l = 0.0, sum_a = 0.0, sum_b = 0.0;
    int hue_hist[180] = {0};
    int brown_count = 0;
    int golden_count = 0;
    int count = 0;

    for (int i = 0; i < total; ++i) {
        if (mask[i] == 0) continue;
        ++count;

        const int idx3 = i * 3;
        const double hv = static_cast<double>(hsv[idx3 + 0]);
        const double sv = static_cast<double>(hsv[idx3 + 1]);
        const double vv = static_cast<double>(hsv[idx3 + 2]);
        const double lv = static_cast<double>(lab[idx3 + 0]);
        const double av = static_cast<double>(lab[idx3 + 1]);
        const double bv = static_cast<double>(lab[idx3 + 2]);

        sum_h += hv;
        sum_s += sv;
        sum_v += vv;
        sum_h2 += hv * hv;
        sum_s2 += sv * sv;
        sum_v2 += vv * vv;
        sum_l += lv;
        sum_a += av;
        sum_b += bv;

        int h_bin = static_cast<int>(hv);
        h_bin = std::max(0, std::min(179, h_bin));
        hue_hist[h_bin] += 1;

        if (hv >= 5.0 && hv <= 25.0) ++brown_count;
        if (hv >= 15.0 && hv <= 35.0) ++golden_count;
    }

    if (count <= 0) {
        return 0;
    }

    const double inv_count = 1.0 / static_cast<double>(count);
    const double mean_h = sum_h * inv_count;
    const double mean_s = sum_s * inv_count;
    const double mean_v = sum_v * inv_count;
    const double mean_l = sum_l * inv_count;
    const double mean_a = sum_a * inv_count;
    const double mean_b = sum_b * inv_count;

    const double var_h = std::max(0.0, sum_h2 * inv_count - mean_h * mean_h);
    const double var_s = std::max(0.0, sum_s2 * inv_count - mean_s * mean_s);
    const double var_v = std::max(0.0, sum_v2 * inv_count - mean_v * mean_v);

    int dominant_hue = 0;
    int dominant_count = hue_hist[0];
    for (int i = 1; i < 180; ++i) {
        if (hue_hist[i] > dominant_count) {
            dominant_count = hue_hist[i];
            dominant_hue = i;
        }
    }

    out_vals[0] = static_cast<double>(count) / static_cast<double>(total);
    out_vals[1] = mean_h;
    out_vals[2] = mean_s;
    out_vals[3] = mean_v;
    out_vals[4] = std::sqrt(var_h);
    out_vals[5] = std::sqrt(var_s);
    out_vals[6] = std::sqrt(var_v);
    out_vals[7] = mean_l;
    out_vals[8] = mean_a;
    out_vals[9] = mean_b;
    out_vals[10] = static_cast<double>(dominant_hue);
    out_vals[11] = mean_s;
    out_vals[12] = mean_v;
    out_vals[13] = static_cast<double>(brown_count) * inv_count;
    out_vals[14] = static_cast<double>(golden_count) * inv_count;
    return 0;
}
