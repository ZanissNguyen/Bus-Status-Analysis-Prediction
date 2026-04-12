ĐẠI HỌC QUỐC GIA THÀNH PHỐ HỒ CHÍ MINH TRƯỜNG ĐẠI HỌC BÁCH KHOA KHOA KHOA HỌC VÀ KỸ THUẬT MÁY TÍNH

Đề tài

HỌC MÁY (CO3117)

"PHÂN TÍCH, DỰ ĐOÁN THỜI GIAN DI CHUYỂN CỦA XE BUÝT TRÊN ĐỊA BÀN TP.HCM"

Giảng viên: Huỳnh Văn Thống

Nhóm: Dreamlite
Sinh viên:

Nguyễn Thành Phát - 2312593

Trần Đỗ Đức Phát - 2312596

Nguyễn Miên Phú - 2312658

THÀNH PHỐ HỒ CHÍ MINH, THÁNG 4 2026

Mục lục

Giới thiệu bài toán và mục tiêu của dự án

1.1 Bối cảnh và động lực

1.2 Vấn đề nghiên cứu và mục tiêu

1.3 Ngữ cảnh dữ liệu

1.4 Các kỹ thuật áp dụng

Tiền xử lý dữ liệu

2.1 Tổng quan về bộ dữ liệu

2.2 Các kỹ thuật tiền xử lý dữ liệu

2.3 Làm giàu dữ liệu và chọn đặc trưng

Huấn luyện mô hình

3.1 Tổng quan bài toán

3.2 Mô hình hóa bài toán

3.2.1 Đặc trưng dữ liệu

3.2.2 Độ đo, đánh giá

3.3 Lựa chọn giải thuật

3.3.1 Linear Regression

3.3.2 Random Forest

3.3.3 Gradient Boosting

3.4 Đánh giá, so sánh giải thuật

Tổng kết và hướng phát triển tương lai

4.1 Tổng kết những đóng góp của đồ án

4.2 Hạn chế của đồ án

4.3 Hướng phát triển tương lai

Tài liệu tham khảo

Danh sách hình ảnh

Hình 1: Random Forest Validation Curve (n_estimators = 50)

Hình 2: Gradient Boosting Validation Curve (n_estimators = 300)

Hình 3: Trực quan hóa so sánh giải thuật

Danh sách bảng

Bảng 1: Hiệu năng các mô hình

1. Giới thiệu bài toán và mục tiêu của dự án

1.1 Bối cảnh và động lực

Hệ thống xe buýt tại Thành phố Hồ Chí Minh là mạng lưới phương tiện giao thông công cộng chủ lực, phục vụ hàng trăm ngàn lượt khách mỗi ngày. Thời gian di chuyển giữa các trạm thường không chính xác do ảnh hưởng bởi nhiều yếu tố ngoại cảnh: mật độ giao thông, thời điểm trong ngày, đặc điểm tuyến đường, điều kiện vận hành... Việc này gây khó chịu cho khách hàng, gây khó khăn trong lên kế hoạch vận hành và tối ưu giao thông đô thị. Mặc dù dữ liệu GPS từ các xe buýt được thu thập liên tục với khối lượng khổng lồ, lượng dữ liệu này chủ yếu mới chỉ được dùng để giám sát tọa độ thụ động. Trong đồ án này, nhóm sử dụng bộ dữ liệu GPS xe buýt trên địa bàn thành phố Hồ Chí Minh để huấn luyện mô hình học máy nhằm dự đoán thời gian di chuyển giữa 2 trạm bất kỳ nhằm hướng tới hỗ trợ quyết định và giao thông thông minh (Smart Mobility).

1.2 Vấn đề nghiên cứu và mục tiêu

Vấn đề cốt lõi là giải quyết bài toán hồi quy bằng cách xây dựng mô hình học máy học có giám sát (supervised) dự đoán thời gian di chuyển giữa trạm A và trạm B dựa trên dữ liệu lịch sử xe buýt.

Mục tiêu cụ thể của dự án bao gồm:

Xây dựng luồng tiền xử lý và làm giàu dữ liệu để làm sạch, gán trạm, và mã hóa, tạo các đặc trưng cho mô hình học.

Thực hiện huấn luyện mô hình bằng nhiều giải thuật để giải quyết bài toán hồi quy. Trong đó thực hiện đánh giá, chọn lựa mô hình.

Trực quan hóa kết quả thành các biểu đồ, bảng để dễ quan sát, từ đó lựa chọn giải thuật để deploy và rút ra các hạn chế (nếu có) để cải thiện.

1.3 Ngữ cảnh dữ liệu

Đồ án sử dụng tập dữ liệu GPS thực tế của mạng lưới xe buýt Thành phố Hồ Chí Minh, bao phủ 31 tuyến xe mang tính đại diện cao [2]. Dữ liệu được thu thập liên tục trong 50 ngày, bao gồm cả ngày thường, cuối tuần và các sự kiện lớn. Tập dữ liệu thô có định dạng JSON với dung lượng lên đến khoảng 34GB, chứa các thuộc tính về không gian, thời gian và trạng thái phần cứng của xe. Đây là một bộ dữ liệu lớn đòi hỏi các quy trình tiền xử lý tinh gọn trước khi đưa vào khai phá.

1.4 Các kỹ thuật áp dụng

Để giải quyết bài toán, đồ án dựa các kỹ thuật, giải thuật trong đề cương môn học, đồng thời mở rộng ứng dụng các quy trình học máy hiện đại:

Huấn luyện mô hình: Đưa mô hình vào pipeline bao gồm preprocessing mô hình sau khi dữ liệu split để tránh data leakage và model.

Lựa chọn mô hình: Dựa vào evaluation curve (biểu đồ tương quan error và độ phức tạp của mô hình) để chọn ra các siêu tham số tối ưu.

Sử dụng và so sánh các giải thuật: Lấy mô hình Linear Regression đơn giản làm baseline để so với 2 mô hình phức tạp hơn là Random Forest (hướng giảm variance) và Gradient Boosting (hướng giảm bias).

1. Tiền xử lý dữ liệu

2.1 Tổng quan về bộ dữ liệu

Tập dữ liệu được sử dụng trong đồ án là dữ liệu cấu trúc dạng JSON, ghi nhận lại hành trình GPS của mạng lưới xe buýt tại Thành phố Hồ Chí Minh. Bộ dữ liệu được thu thập liên tục trong 50 ngày (từ 20/03 đến 10/05/2025), bao phủ 31 tuyến xe tiêu biểu với các đặc điểm đa dạng về chiều dài, tần suất và mật độ trạm dừng. Sau khi giải nén, tập dữ liệu gốc có dung lượng khoảng 34GB, chứa hàng chục triệu bản ghi tọa độ theo thời gian thực. Mỗi bản ghi bao gồm các trường thông tin cơ bản như: mã số xe, thời gian, kinh độ, vĩ độ, tốc độ hiện tại, và trạng thái đóng mở của cửa trước và cửa sau,...

2.2 Các kỹ thuật tiền xử lý dữ liệu

Do đặc thù dung lượng lớn và chứa nhiều nhiễu từ thiết bị phần cứng, quy trình tiền xử lý được chia thành các bước làm sạch và thu gọn nghiêm ngặt nhằm tối ưu hóa không gian lưu trữ và tốc độ tính toán:

Tích hợp và thu gọn dữ liệu: Dữ liệu thô bao gồm 356 tệp JSON rời rạc được tích hợp thành một tệp định dạng Parquet duy nhất. Quá trình này giúp giảm đáng kể dung lượng lưu trữ và tăng tốc độ đọc dữ liệu lên nhiều lần. Đồng thời, các thuộc tính không mang lại giá trị cho bài toán phân tích giao thông như hướng la bàn, trạng thái điều hòa, cờ đánh dấu xe chở học sinh và trạng thái nổ máy đều được loại bỏ.

Khử trùng lặp và xử lý giá trị khuyết: Các bản ghi bị trùng lặp thời gian phát tín hiệu trên cùng một phương tiện được loại bỏ. Đối với các giá trị khuyết, đồ án áp dụng quy tắc mặc định an toàn: dữ liệu khuyết tốc độ được điền giá trị 0, dữ liệu khuyết trạng thái cửa được mặc định là đóng. Các bản ghi bị mất hoàn toàn thông tin tọa độ sẽ bị xóa bỏ triệt để khỏi tập dữ liệu.

Lọc nhiễu không gian: Để loại bỏ các sai số phần cứng khiến tọa độ GPS bị văng ra khỏi khu vực hoạt động, đồ án thiết lập một ranh giới địa lý bao quanh Thành phố Hồ Chí Minh và các tỉnh lân cận. Mọi tọa độ nằm ngoài ranh giới kinh độ và vĩ độ này đều bị loại trừ.

2.3 Làm giàu dữ liệu và chọn đặc trưng

Sau khi làm sạch, dữ liệu GPS thô được làm giàu thêm các ngữ cảnh về không gian và vận hành để chuẩn bị cho quá trình khai phá:

Ánh xạ trạm bằng thuật toán BallTree: Đây là kỹ thuật cốt lõi để kết nối tọa độ GPS với mạng lưới giao thông. Đồ án xây dựng cấu trúc cây BallTree dựa trên tọa độ của toàn bộ trạm xe buýt và sử dụng công thức Haversine để tính khoảng cách hình cầu. Đối với mỗi điểm GPS, thuật toán sẽ truy vấn trạm gần nhất và gán tên trạm, khoảng cách đến trạm, và cờ đánh dấu bến cuối vào bản ghi. Các điểm GPS cách trạm quá 1000 mét sẽ bị loại bỏ vì không thuộc phạm vi mạng lưới xe buýt.

Tạo đặc trưng mới: Dữ liệu được tính toán, mã hóa các thuộc tính mới như:

Thời gian trong ngày: Thời gian có tính tuần hoàn đặc trưng hour được mã hóa sang biểu diễn lượng giác: hour -> {hour_sin, hour_cos}, giúp mô hình học được tính liên tục giữa các mốc thời gian gần nhau (ví dụ 23h và 0h).

Xây dựng đặc trưng tuyến đường (route): Các chuyến đi được gộp thành một định danh tuyến route = (start, end) nhằm phân biệt hướng di chuyển giữa hai điểm. Thời gian trung bình lịch sử của mỗi tuyến được tính toán để cung cấp thông tin nền (historical prior) cho mô hình.

Đặc trưng lịch sử (average route duration): Thực hiện thống kê thời gian trung bình đi một tuyến, của điểm bắt đầu và của điểm kết thúc. Các đặc trưng này chỉ được tính toán trên tập huấn luyện. Đồng thời thực hiện chiến lược fallback cho những đặc trưng này trong tập kiểm thử theo phân cấp để đảm bảo mô hình vẫn khai thác được thông tin giao thông ở mức tổng quát hơn khi dữ liệu chi tiết không tồn tại:

avg_route_duration $\rightarrow$ avg_start_duration $\rightarrow$ avg_end_duration $\rightarrow$ avg_global_duration

1. Huấn luyện mô hình

3.1 Tổng quan bài toán

3.2 Mô hình hóa bài toán

Bài báo cáo hướng đến bài toán ETA (The Estimated Time of Arrival) về thời gian di chuyển trong địa bàn thành phố Hồ Chí Minh. Với mục đích dự đoán được thời gian đi xe buýt từ trạm A đến trạm B trong khung giờ nhất định.

Với mỗi mẫu dữ liệu đại diện cho một đoạn đi của xe buýt và được mô hình hóa thành bài toán supervised regression như sau:

$$ETA\_duration = f(start\_station, end\_station, distance, weekend, hour, route\_avg\_duration)$$

Cụ thể mô hình bao gồm:

Input (X):

Start station: Tên Trạm Đi

End station: Tên Trạm Đến

Distance: Khoảng tính theo GPS

Weekend: Có phải cuối tuần (thứ bảy, chủ nhật)

Hour: Giờ bắt đầu

Route average duration: Thời gian đi trung bình tính từ dữ liệu

Output (Y):

Duration: Khoảng cách ước tính đi giữa 2 chuyến $\in \mathbb{R}$

Bài toán trên là một dạng bài practical regression (ứng dụng hồi quy) với dữ liệu thu thập GPS thực tế từ hệ thống giám sát gửi từ nhiều nguồn (nhiều xe) và tương đối nhiều nhiễu cần xử lý.

3.2.1 Đặc trưng dữ liệu

Thứ nhất - Real-world noise: Bộ dữ liệu cho bài toán thu thập từ các thiết bị định vị GPS có nhiều nhiễu. Mặc dù đã qua bước tiền xử lý để làm sạch nhưng vẫn cần làm sạch lại các chuyến dài, lâu bất thường do thông tin bị mất, thiếu.

Thứ hai - Semi-Temporal (tính bán thời gian): Bộ dữ liệu có các thông tin liên quan đến thời gian, tuy nhiên bộ dữ liệu này không hoàn toàn là một chuỗi time-series. Mỗi mẫu là một chuyến đi riêng biệt trong một khung giờ trong ngày nhất định. Mặc dù vậy các thuộc tính thời gian như ngày, giờ lại đóng góp vào suy luận các "tri thức" (pattern) liên quan tình trạng giao thông (xác định giờ cao điểm, cuối tuần thì đông/ít người đi hơn).

Thứ ba - Near-Linear Physic Relationship: Mối quan hệ giữa thời gian di chuyển và khoảng cách gần như là tuyến tính về mặt vật lý theo công thức: $duration = \frac{distance}{avg\_speed}$. Tuy nhiên, trong thực tế thời gian di chuyển còn bị ảnh hưởng nhiều bởi tình trạng, mật độ giao thông, thời gian trong ngày, đặc trưng của tuyến... điều này nghĩa là các mô hình, giải thuật học tuyến tính, phi tuyến tính đều có hiệu quả nhất định.

Tóm lại, cũng vì các đặc trưng dữ liệu được đề cập trên thì historical feature: average_duration được tính toán sẽ ảnh hưởng lớn đến kết quả của mô hình, các feature phi tuyến tính khác chỉ ảnh hưởng một phần.

3.2.2 Độ đo, đánh giá

Để đánh giá, so sánh các giải thuật nhóm sử dụng ba độ đo cho bài toán hồi quy bao gồm:

Mean Absolute Error (MAE): Phản ánh sai số theo giây, ít nhạy với nhiễu.

$$MAE = \frac{1}{n}\sum_{i=1}^{n}|y_{i}-\hat{y}_{i}|$$

Root Mean Squared Error (RMSE): Đánh giá tính ổn định và độ nhạy với các dự đoán bất thường, phạt rất nặng với nhiễu. Đặc biệt là trong bài toán ETA giúp giảm các lỗi dự đoán, cải thiện đáng kể trải nghiệm người dùng.

$$RMSE = \sqrt{\frac{1}{n}\sum_{i=1}^{n}(y_{i}-\hat{y}_{i})^{2}}$$

$R^2$ Score ($R^2$): Phản ánh khả năng giải thích các sai số của mô hình. Hỗ trợ so sánh các mô hình với nhau.

$$R^2 = 1 - \frac{\sum_{i=1}^{n}(y_{i}-\hat{y}_{i})^{2}}{\sum_{i=1}^{n}(y_{i}-\overline{y})^{2}}$$

$R^2 = 1$: Mô hình giải thích được toàn bộ sai số.

$R^2 = 0$: Mô hình có hiệu năng như lấy trung bình.

$R^2 < 0$: Mô hình tệ hơn cả việc lấy tất cả dự đoán là trung bình.

Với bộ dữ liệu về các tuyến xe buýt này, thời gian đi giữa các chuyến có độ chênh lệch cao, một số chuyến ngắn chỉ dài 1-2 phút trong khi có chuyến dài đến 5-10 phút hơn. Do đó việc tính MAE và RMSE trực tiếp trên toàn bộ dữ liệu (global evaluation) có thể dẫn đến sự sai lệch về hiệu năng dự đoán một số tuyến. Cụ thể cùng MAE là 60s nhưng với chuyến ngắn thì là sai số rất lớn còn với chuyến dài thì hiệu năng được đánh giá cao.

Do đó, để đảm bảo tính công bằng giữa các tuyến thì MAE và RMSE được tính riêng từng route, sau được chuẩn hóa và lấy trung bình. Giá trị cuối cùng được tính bằng trung bình của các độ đo đã chuẩn hóa trên tất cả các route, giúp mỗi tuyến đóng góp ngang nhau vào quá trình đánh giá mô hình.

Cách đánh giá này phù hợp với các hệ thống dự đoán ETA trong thực tế, nơi sai số tương đối quan trọng hơn sai số tuyệt đối nhằm đảm bảo trải nghiệm người dùng nhất quán trên các tuyến đường khác nhau.

3.3 Lựa chọn giải thuật

Nhóm phân tích hành vi học của các mô hình sau đó lựa chọn độ phức tạp phù hợp.

3.3.1 Linear Regression

Giải thuật giả định mối quan hệ tuyến tính giữa mục tiêu và các tham số đầu vào. Các tham số đầu vào cần chuẩn hóa (StandardScaler). Với công thức:

$$y = \beta_{0} + \sum_{i=1}^{p}\beta_{i}x_{i} + \epsilon$$

Là mô hình đơn giản và tương đối phù hợp với bộ dữ liệu gần tuyến tính, chịu tác động mạnh bởi các dữ liệu nhiễu.

3.3.2 Random Forest

Giải thuật thuộc nhóm ensemble, xây nhiều cây quyết định độc lập với nhau rồi tính trung bình lại các cây để đưa ra một cây cuối cùng. Giải thuật có khả năng học các mối quan hệ phi tuyến tính, giảm nhanh phương sai và thường hội tụ tương đối sớm. Với công thức:

$$\hat{y} = \frac{1}{T}\sum_{t=1}^{T}Tree_{t}(x)$$

Số cây ước lượng được lựa chọn dựa trên model complexity curve hay validation curve của lần học với n_estimators = 50 như trong hình 1. Có thể thấy mô hình hội tụ tương đối sớm và ổn định hiệu năng trong khoảng 40 cây.

Hình 1: Random Forest Validation Curve ($n\_estimators = 50$)

3.3.3 Gradient Boosting

Cũng là một giải thuật thuộc nhóm ensemble, tạo một cây ban đầu rồi tuần tự cải thiện cây đó qua nhiều giai đoạn (boosting stages). Giải thuật học từ các lỗi sai của cây trước từ đó mà cải thiện dần. Có công thức:

$$F_{m}(x) = F_{m-1}(x) + \gamma h_{m}(x)$$

Số boosting stage được lựa chọn theo validation curve của lần học với n_estimators = 300 như trong hình 2. Từ mô hình nhóm thấy hiệu năng của mô hình bão hòa và chi phí tính toán gần tối ưu ở khoảng 150 boosting stage.

Hình 2: Gradient Boosting Validation Curve ($n\_estimators = 300$)

3.4 Đánh giá, so sánh giải thuật

Các siêu tham số được quyết định từ Validation Curve được dùng để cấu hình mô hình cuối để so sánh và đánh giá các giải thuật. Từ ba mô hình được huấn luyện với cùng một bộ dữ liệu và các siêu tham số được đề cập như trên ta thu được kết quả như bảng 1:

Bảng 1: Hiệu năng các mô hình

Model

MAE

RMSE

$R^2$

Linear Regression

0.287421

0.345998

0.632395

Random Forest (n=40)

0.278868

0.352457

0.651867

Gradient Boosting (n=150)

0.281841

0.338882

0.659763

Hình 3: Trực quan hóa so sánh giải thuật

Bảng 1 cho thấy, về MAE mô hình Random Forest mang lại hiệu năng tốt nhất, tiếp đến là Gradient Boosting và sau cùng là Linear Regression. Đối với độ đo RMSE Gradient Boosting và Random Forest gần như ngang nhau và đều tốt hơn Linear Regression. Tuy nhiên ở độ đo $R^2$ Gradient Boosting dẫn đầu, có hiệu năng tốt hơn Random Forest và tệ nhất là Linear Regression.

Bộ dữ liệu dùng để huấn luyện và kiểm thử chủ yếu thể hiện mối quan hệ tuyến tính, chỉ tồn tại một số tương tác phi tuyến tính nhỏ thực sự tồn tại (hour, weekend). Đồng thời việc xây dựng các historical features (avg_route_duration...) khiến bài toán này trở thành historical lookup + small nonlinear correction. Do đó các mô hình tuyến tính vẫn mang lại hiệu năng tương đối, trong khi mô hình cây (base-tree) có thể học được các pattern nhỏ phi tuyến tính.

Random Forest giữ mức ổn định cao do cơ chế giảm phương sai thông qua việc lấy trung bình các cây được huấn luyện độc lập, dẫn đến các giá trị MAE và RMSE giữ ở mức thấp và ổn định. Ngược lại, Gradient Boosting học, tối ưu tuần tự từ cây trước, cho phép bắt được các mẫu, nhiễu phức tạp hơn và đạt điểm $R^2$ cao hơn.

Mặc dù có sự sai lệch về hiệu năng nhưng nhìn chung khoảng cách hiệu năng giữa ba mô hình không lớn. Linear Regression, dù là mô hình đơn giản, chỉ kém hơn mô hình Gradient Boosting $R^2 \sim 0.02$. Điều này chỉ ra rằng trong bài toán hiện tại giới hạn không nằm ở độ phức tạp của mô hình mà chủ yếu đến từ chất lượng và độ đầy đủ của dữ liệu.

Giá trị $R^2 \approx 60\%$ ở cả ba mô hình cho thấy còn nhiều đặc trưng ẩn, nguồn biến thiên chưa được tìm thấy, chẳng hạn như: thời tiết, mật độ giao thông trên tuyến đường, đèn tín hiệu giao thông, tình trạng ùn tắc trên tuyến giao thông trước đó... vốn chưa được phản ánh trong dữ liệu hiện tại.

1. Tổng kết và hướng phát triển tương lai

4.1 Tổng kết những đóng góp của đồ án

Đồ án đã hoàn thành mục tiêu đặt ra từ đầu là xây dựng mô hình dự đoán thời gian di chuyển giữa hai trạm A và B dựa theo dữ liệu GPS xe buýt trên địa bàn thành phố Hồ Chí Minh. Nhóm nghiên cứu đã xây dựng pipeline hoàn chỉnh gồm: xử lý dữ liệu trước split, xây dựng các đặc trưng cần thiết cho mô hình, xử lý dữ liệu sau khi split dữ liệu, thiết lập pipeline mô hình, huấn luyện và tối ưu các mô hình, lựa chọn mô hình, so sánh các mô hình.

Nhóm nghiên cứu đã xây dựng thành công mô hình với 3 giải thuật (Linear Regression, Random Forest, Gradient Boosting). Và chọn mô hình Random Forest để deploy do tính ổn định của mô hình giúp tối ưu trải nghiệm người dùng. Thông qua quá trình đó đúc kết được kiến thức về xử lý dữ liệu, lựa chọn mô hình, xây dựng các đặc trưng sao cho tránh data leakage cũng như một số chiến lược xử lý non-seen value.

4.2 Hạn chế của đồ án

Mặc dù đạt được những kết quả, đồ án vẫn còn tồn tại một số giới hạn nhất định:

Về quy mô dữ liệu: Hệ thống hiện tại chỉ mới huấn luyện mô hình bằng một phần nhỏ trên tập dữ liệu mẫu gồm 31 tuyến xe buýt trong phạm vi 50 ngày. Mặc dù đây là các tuyến trọng điểm, việc chưa bao quát toàn bộ mạng lưới giao thông của thành phố khiến cho một số chuỗi lây lan ách tắc diện rộng xuyên tuyến có thể chưa được khám phá trọn vẹn.

Về tiền xử lý dữ liệu: Dữ liệu xử lý còn khá "nông" chưa đúc kết được nhiều dữ liệu giá trị, còn nhiều vấn đề chưa được giải quyết như phân biệt noise thật và các trường hợp hiếm mà trong đồ án này chỉ thực hiện xử lý bằng các ngưỡng nhất định.

Về xây dựng các đặc trưng: Theo kết quả so sánh hiệu quả mô hình là xấp xỉ nhau giữa Linear Regression, Random Forest và Gradient Boosting cũng như vấn đề trong khâu tiền xử lý mà các đặc trưng đầu vào và dữ liệu hiện đang là giới hạn của bài toán. Hay các mô hình đã học được hết các pattern từ dữ liệu đơn giản hiện tại nhưng chưa giải thích được toàn bộ các sai số ($R^2 \approx 60\%$).

4.3 Hướng phát triển tương lai

Dựa trên những nền tảng vững chắc đã xây dựng và các hạn chế còn tồn đọng, đồ án đề xuất các hướng phát triển tiếp theo như sau:

Tích hợp dữ liệu đa nguồn: Mở rộng không gian đặc trưng bằng cách thu thập và tích hợp thêm các nguồn dữ liệu ngoại cảnh như tình hình thời tiết, lịch sự kiện lễ hội, hoặc dữ liệu từ hệ thống camera giao thông. Việc làm giàu dữ liệu này sẽ giúp giải thích sâu hơn nguyên nhân gốc rễ của các điểm đen kẹt xe ngẫu nhiên.

Mô hình hóa yếu tố thời gian (Temporal Modeling): Thời gian di chuyển của xe buýt mang tính phụ thuộc theo chuỗi thời gian, giao thông tại một thời điểm thường chịu ảnh hưởng từ trạng thái trước. Trong đồ án hiện tại, mỗi mẫu dữ liệu được xem là độc lập, do đó mô hình chưa khai thác được tính liên tục theo thời gian của hệ thống giao thông. Trong tương lai, có thể mở rộng bằng cách xây dựng các sliding window features, thống kê ngắn hạn hoặc áp dụng các mô hình chuyên cho dữ liệu chuỗi thời gian như Long Short-Term Memory (LSTM).

Mô hình hóa cấu trúc mạng lưới giao thông (Route, station relation): Các tuyến, trạm xe buýt trong đô thị không tồn tại độc lập mà liên kết với nhau tạo thành một mạng lưới giao thông phức tạp, trong đó tình trạng tắc nghẽn tại một tuyến có thể lan sang các tuyến lân cận thông qua các nút giao quan trọng. Việc biểu diễn dữ liệu như hiện tại cũng như việc xử lý OneHotEncoding với các đặc trưng trạm chưa phản ánh đầy đủ mối quan hệ không gian này. Hướng phát triển trước mắt là thay thế OneHotEncoding bằng một phương pháp mã hóa khác trong đó thể hiện được mối quan hệ giữa các trạm (gần giống Embedding), còn về lâu dài có thể thực hiện mô hình hóa lại toàn bộ dữ liệu dưới dạng đồ thị mà mỗi trạm là một node.

Học thích nghi và cập nhật mô hình theo thời gian (Adaptive / Online Learning): Điều kiện giao thông đô thị thay đổi liên tục theo thời gian do sự phát triển hạ tầng, thay đổi luồng phương tiện hoặc các chính sách đổi mới. Mô hình trong đồ án được huấn luyện bằng phương pháp batch offline (train một lần trên tập dữ liệu thu thập từ trước) bị ảnh hưởng khi dữ liệu thực tế thay đổi. Do đó tương lai có thể xây dựng cơ chế cập nhật định kỳ hoặc áp dụng các phương pháp online learning, cho phép mô hình học bổ sung từ dữ liệu mới mà không cần huấn luyện lại hoàn toàn, từ đó duy trì độ chính xác dự đoán trong môi trường vận hành thực tế dài hạn.

1. Tài liệu tham khảo

[1] Leo Breiman. Random forests. Machine Learning, 45(1):5-32, 2001.

[2] Khang Nguyen Duy and Nam Thoai. Ho chi minh city bus gps dataset. Kaggle Dataset, 2025. Truy cập ngày 6 tháng 4 năm 2026.

[3] Jerome H. Friedman. Greedy function approximation: A gradient boosting machine. Annals of Statistics, 2001.

[4] Trevor Hastie, Robert Tibshirani, and Jerome Friedman. The Elements of Statistical Learning: Data Mining, Inference, and Prediction. Springer, 2 edition, 2009.

[5] Gareth James, Daniela Witten, Trevor Hastie, and Robert Tibshirani. An Introduction to Statistical Learning. Springer, 2 edition, 2021.

[6] Fabian Pedregosa, Gael Varoquaux, Alexandre Gramfort, et al. Scikit-learn: Machine learning in python. Journal of Machine Learning Research, 12:2825-2830, 2011.
