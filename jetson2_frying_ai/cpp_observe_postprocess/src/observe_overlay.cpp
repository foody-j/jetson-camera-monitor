#include <cstdint>
#include <vector>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

extern "C" int build_overlay_jpeg(
    const uint8_t* frame_bgr,
    const uint8_t* mask,
    int src_h,
    int src_w,
    int target_w,
    int jpeg_quality,
    uint8_t* out_buf,
    int out_capacity,
    int* out_size
) {
    if (!frame_bgr || !mask || !out_buf || !out_size || src_h <= 0 || src_w <= 0 || target_w <= 1 || out_capacity <= 0) {
        return -1;
    }

    const int target_h = static_cast<int>((static_cast<double>(src_h) * target_w) / (src_w > 0 ? src_w : 1));
    if (target_h <= 1) {
        return -2;
    }

    cv::Mat src(src_h, src_w, CV_8UC3, const_cast<uint8_t*>(frame_bgr));
    cv::Mat src_mask(src_h, src_w, CV_8UC1, const_cast<uint8_t*>(mask));

    cv::Mat small;
    cv::resize(src, small, cv::Size(target_w, target_h), 0, 0, cv::INTER_LINEAR);
    if (small.empty()) {
        return -3;
    }

    cv::Mat mask_small;
    cv::resize(src_mask, mask_small, cv::Size(target_w, target_h), 0, 0, cv::INTER_NEAREST);
    if (mask_small.empty()) {
        return -4;
    }

    if (cv::countNonZero(mask_small) == 0) {
        return 0;
    }

    cv::Mat overlay = small.clone();
    for (int y = 0; y < target_h; ++y) {
        const uint8_t* mrow = mask_small.ptr<uint8_t>(y);
        const cv::Vec3b* srow = small.ptr<cv::Vec3b>(y);
        cv::Vec3b* orow = overlay.ptr<cv::Vec3b>(y);
        for (int x = 0; x < target_w; ++x) {
            if (mrow[x] > 0) {
                orow[x][0] = static_cast<uint8_t>(srow[x][0] * 0.65);
                orow[x][1] = static_cast<uint8_t>(srow[x][1] * 0.65 + 255.0 * 0.35);
                orow[x][2] = static_cast<uint8_t>(srow[x][2] * 0.65);
            }
        }
    }

    std::vector<uint8_t> encoded;
    const std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, jpeg_quality};
    if (!cv::imencode(".jpg", overlay, encoded, params)) {
        return -5;
    }
    if (static_cast<int>(encoded.size()) > out_capacity) {
        return -6;
    }

    std::copy(encoded.begin(), encoded.end(), out_buf);
    *out_size = static_cast<int>(encoded.size());
    return 1;
}
