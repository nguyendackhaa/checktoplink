document.addEventListener("DOMContentLoaded", function () {
  // Các phần tử DOM
  const rankForm = document.getElementById("rankForm");
  const keywordInput = document.getElementById("keyword");
  const urlInput = document.getElementById("url");
  const countrySelect = document.getElementById("country");
  const checkButton = document.getElementById("checkButton");
  const loadingSpinner = document.getElementById("loadingSpinner");
  const resultDiv = document.getElementById("result");
  const rankNumber = document.getElementById("rankNumber");
  const rankText = document.getElementById("rankText");
  const rankDetails = document.getElementById("rankDetails");
  const refreshHistoryBtn = document.getElementById("refreshHistory");
  const historyBody = document.getElementById("historyBody");

  // Tải lịch sử kiểm tra khi trang được tải
  loadHistory();

  // Xử lý form kiểm tra thứ hạng
  rankForm.addEventListener("submit", function (e) {
    e.preventDefault();

    const keyword = keywordInput.value.trim();
    const url = urlInput.value.trim();
    const country = countrySelect.value;

    if (!keyword || !url) {
      alert("Vui lòng nhập đầy đủ từ khóa và URL.");
      return;
    }

    // Hiển thị loading
    checkButton.disabled = true;
    loadingSpinner.classList.remove("d-none");
    resultDiv.classList.add("d-none");

    // Gửi yêu cầu kiểm tra thứ hạng
    fetch("/api/check-ranking", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        keyword: keyword,
        url: url,
        country: country,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        // Hiển thị kết quả
        showResult(data);

        // Cập nhật lịch sử
        loadHistory();

        // Kết thúc loading
        checkButton.disabled = false;
        loadingSpinner.classList.add("d-none");
      })
      .catch((error) => {
        console.error("Lỗi:", error);
        alert("Đã xảy ra lỗi khi kiểm tra thứ hạng. Vui lòng thử lại sau.");

        checkButton.disabled = false;
        loadingSpinner.classList.add("d-none");
      });
  });

  // Nút làm mới lịch sử
  refreshHistoryBtn.addEventListener("click", loadHistory);

  // Hàm hiển thị kết quả
  function showResult(data) {
    resultDiv.classList.remove("d-none");

    if (data.rank > 0) {
      // Tìm thấy URL trong kết quả tìm kiếm
      rankNumber.textContent = data.rank;
      rankText.textContent = `Thứ hạng: ${data.rank}`;
      rankDetails.textContent = `URL "${data.url}" đứng thứ ${
        data.rank
      } cho từ khóa "${data.keyword}" tại ${getCountryName(data.country)}.`;

      // Đổi màu theo thứ hạng
      const rankCircle = document.querySelector(".rank-circle");
      rankCircle.classList.remove("not-found");

      if (data.rank <= 10) {
        rankCircle.style.backgroundColor = "#198754"; // Xanh lá (tốt)
      } else if (data.rank <= 30) {
        rankCircle.style.backgroundColor = "#0d6efd"; // Xanh dương (trung bình)
      } else if (data.rank <= 50) {
        rankCircle.style.backgroundColor = "#fd7e14"; // Cam (thấp)
      } else {
        rankCircle.style.backgroundColor = "#dc3545"; // Đỏ (rất thấp)
      }
    } else {
      // Xử lý các mã lỗi khác nhau
      const rankCircle = document.querySelector(".rank-circle");
      rankCircle.classList.add("not-found");
      rankCircle.style.backgroundColor = "#dc3545"; // Đỏ

      if (data.rank === -2 || data.error_code === "CAPTCHA_REQUIRED") {
        // Lỗi CAPTCHA
        rankNumber.textContent = "!";
        rankText.textContent = "Google yêu cầu CAPTCHA";
        rankDetails.innerHTML =
          'Google đang chặn yêu cầu tự động. Vui lòng thử lại sau hoặc <a href="/debug" target="_blank">xem thông tin debug</a> để biết thêm chi tiết.';
      } else if (data.rank === -3 || data.error_code === "CONNECTION_ERROR") {
        // Lỗi kết nối
        rankNumber.textContent = "!";
        rankText.textContent = "Lỗi kết nối";
        rankDetails.innerHTML =
          'Không thể kết nối đến Google sau nhiều lần thử. Vui lòng kiểm tra kết nối mạng và thử lại sau. <a href="/debug" target="_blank">Xem chi tiết</a>';
      } else {
        // Không tìm thấy URL
        rankNumber.textContent = "?";
        rankText.textContent = "Không tìm thấy";
        rankDetails.innerHTML = `URL "${
          data.url
        }" không xuất hiện trong 100 kết quả đầu tiên cho từ khóa "${
          data.keyword
        }" tại ${getCountryName(
          data.country
        )}. <a href="/debug" target="_blank">Xem debug</a>`;
      }
    }
  }

  // Hàm tải lịch sử kiểm tra
  function loadHistory() {
    fetch("/api/history")
      .then((response) => response.json())
      .then((data) => {
        historyBody.innerHTML = "";

        if (data.length === 0) {
          const row = document.createElement("tr");
          row.innerHTML =
            '<td colspan="5" class="text-center py-3">Chưa có lịch sử kiểm tra nào</td>';
          historyBody.appendChild(row);
          return;
        }

        // Sắp xếp lịch sử theo thời gian mới nhất
        data.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        // Hiển thị tối đa 10 bản ghi gần nhất
        data.slice(0, 10).forEach((item) => {
          const row = document.createElement("tr");

          let rankText = "";
          if (item.rank === -2) {
            rankText =
              '<span class="badge bg-warning text-dark">CAPTCHA</span>';
          } else if (item.rank > 0) {
            rankText = `<span class="badge bg-${getRankBadgeColor(
              item.rank
            )}">${item.rank}</span>`;
          } else {
            rankText = '<span class="badge bg-danger">Không tìm thấy</span>';
          }

          row.innerHTML = `
                        <td>${formatDateTime(item.timestamp)}</td>
                        <td>${item.keyword}</td>
                        <td><span class="limited-url" title="${item.url}">${
            item.url
          }</span></td>
                        <td>${getCountryName(item.country)}</td>
                        <td>${rankText}</td>
                    `;

          historyBody.appendChild(row);
        });
      })
      .catch((error) => {
        console.error("Lỗi khi tải lịch sử:", error);
        historyBody.innerHTML =
          '<tr><td colspan="5" class="text-center text-danger py-3">Lỗi khi tải lịch sử</td></tr>';
      });
  }

  // Hàm định dạng thời gian
  function formatDateTime(dateTimeStr) {
    const date = new Date(dateTimeStr);
    return (
      date.toLocaleDateString("vi-VN") + " " + date.toLocaleTimeString("vi-VN")
    );
  }

  // Hàm lấy màu cho badge thứ hạng
  function getRankBadgeColor(rank) {
    if (rank <= 10) return "success";
    if (rank <= 30) return "primary";
    if (rank <= 50) return "warning";
    return "danger";
  }

  // Hàm lấy tên quốc gia từ mã quốc gia
  function getCountryName(countryCode) {
    const countries = {
      vn: "Việt Nam",
      us: "Hoa Kỳ",
      jp: "Nhật Bản",
      uk: "Anh",
      sg: "Singapore",
      au: "Úc",
    };

    return countries[countryCode] || countryCode;
  }
});
