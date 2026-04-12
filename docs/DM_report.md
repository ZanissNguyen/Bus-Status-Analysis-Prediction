ĐẠI HỌC QUỐC GIA THÀNH PHỐ HỒ CHÍ MINH TRƯỜNG ĐẠI HỌC BÁCH KHOA KHOA KHOA HỌC VÀ KỸ THUẬT MÁY TÍNH

KHAI PHÁ DỮ LIỆU (CO3029)

BÁO CÁO BÀI TẬP LỚN

Khai phá dữ liệu GPS của mạng lưới xe buýt TP.HCM để phát hiện điểm đen kẹt xe và hiện tượng dồn chuyến

Github: Zaniss Nguyen/Bus-Status-Analysis-Prediction

GVHD: Ths Đỗ Thanh Thái

SV thực hiện:

Nguyễn Miên Phú - 2312658

Trần Đỗ Đức Phát - 2312596

Nguyễn Thành Phát - 2312593

TP Hồ Chí Minh, Tháng 5 Năm 2026

Mục lục

Giới thiệu bài toán và mục tiêu của dự án

1.1 Bối cảnh và động lực

1.2 Vấn đề nghiên cứu và mục tiêu

1.3 Hỗ trợ ra quyết định và tính thực tiễn

1.4 Ngữ cảnh dữ liệu

1.5 Các kỹ thuật khai phá dữ liệu áp dụng

Tiền xử lý dữ liệu

2.1 Tổng quan về bộ dữ liệu

2.2 Các kỹ thuật tiền xử lý dữ liệu

2.3 Làm giàu dữ liệu và chọn đặc trưng

2.4 Phân tích và lựa chọn các tham số nghiệp vụ

Phương pháp khai phá dữ liệu

3.1 Nhận diện tuyến đường với thuật toán FP-Growth

3.2 Phân cụm điểm đen giao thông với thuật toán HDBSCAN

3.3 Khai phá chuỗi lây lan kẹt xe với thuật toán PrefixSpan

Kết quả thực nghiệm và phân tích

4.1 Kết quả phân cụm điểm đen giao thông

4.2 Kết quả phân tích hiện tượng dồn chuyến và thủng tuyến

4.3 Kết quả khai phá chuỗi lây lan điểm đen kẹt xe

4.4 Kết quả phân tích chuỗi hiệu ứng dây chuyền vận hành

4.5 Đánh giá mức độ đáp ứng mục tiêu

Trình diễn tri thức và ứng dụng

5.1 Xây dựng hệ thống bảng điều khiển tương tác

5.2 Trực quan hóa kết quả khai phá

5.3 Ứng dụng hỗ trợ ra quyết định (kịch bản thực tế)

Tổng kết và hướng phát triển tương lai

6.1 Tổng kết những đóng góp của đồ án

6.2 Hạn chế của đồ án

6.3 Hướng phát triển tương lai

Tài liệu tham khảo

1. Giới thiệu bài toán và mục tiêu của dự án

1.1 Bối cảnh và động lực

Hệ thống xe buýt tại Thành phố Hồ Chí Minh là mạng lưới phương tiện giao thông công cộng chủ lực, phục vụ hàng trăm ngàn lượt khách mỗi ngày. Tuy nhiên, dưới áp lực của điều kiện giao thông phức tạp, hệ thống thường xuyên đối mặt với các vấn đề vận hành nghiêm trọng như hiện tượng dồn tuyến (bus bunching) [5] và ách tắc tại các điểm đen giao thông. Mặc dù dữ liệu GPS từ các xe buýt được thu thập liên tục với khối lượng khổng lồ, lượng dữ liệu này chủ yếu mới chỉ được dùng để giám sát tọa độ thụ động. Động lực của đồ án này là áp dụng các kỹ thuật khai phá dữ liệu để trích xuất những quy luật ẩn từ luồng dữ liệu GPS thô, qua đó chuyển hóa dữ liệu thành tri thức phục vụ công tác điều phối.

1.2 Vấn đề nghiên cứu và mục tiêu

Vấn đề cốt lõi của đồ án là giải quyết bài toán hộp đen trong vận hành: thiếu công cụ để tự động phát hiện các điểm nghẽn giao thông và không nắm bắt được chuỗi hiệu ứng dây chuyền khi hiện tượng kẹt xe hoặc dồn chuyến xảy ra.

Mục tiêu cụ thể của dự án bao gồm:

Xây dựng luồng tiền xử lý và làm giàu dữ liệu để làm sạch, gán trạm, và nhận diện tuyến đường từ luồng dữ liệu GPS thô.

Ứng dụng các thuật toán khai phá dữ liệu để tự động phân cụm các vùng kẹt xe, tìm ra các chuỗi lây lan điểm đen giao thông và phân tích hiệu ứng dây chuyền của hiện tượng dồn chuyến.

Trực quan hóa kết quả thành các bảng điều khiển tương tác để người dùng dễ dàng theo dõi và đánh giá tình hình.

1.3 Hỗ trợ ra quyết định và tính thực tiễn

Kết quả từ đồ án cung cấp một hệ thống hỗ trợ ra quyết định trực quan cho trung tâm quản lý giao thông công cộng. Dựa trên các tri thức khai phá được, ví dụ như phát hiện chính xác khu vực nào là khởi nguồn của hiệu ứng lây lan kẹt xe hàng loạt, ban quản lý có thể đưa ra các quyết định can thiệp tức thời như điều hướng luồng tuyến, phân bổ lại xe dự phòng, giãn cách chuyến hoặc tối ưu hóa lịch trình dài hạn.

1.4 Ngữ cảnh dữ liệu

Đồ án sử dụng tập dữ liệu GPS thực tế của mạng lưới xe buýt Thành phố Hồ Chí Minh, bao phủ 31 tuyến xe mang tính đại diện cao [1]. Dữ liệu được thu thập liên tục trong 50 ngày, bao gồm cả ngày thường, cuối tuần và các sự kiện lớn. Tập dữ liệu thô có định dạng JSON với dung lượng lên đến khoảng 34GB, chứa các thuộc tính về không gian, thời gian và trạng thái phần cứng của xe. Đây là một bộ dữ liệu lớn đòi hỏi các quy trình tiền xử lý tinh gọn trước khi đưa vào khai phá.

1.5 Các kỹ thuật khai phá dữ liệu áp dụng

Để giải quyết bài toán, đồ án bám sát các kỹ thuật cốt lõi trong đề cương môn học, đồng thời mở rộng ứng dụng các thuật toán tiên tiến:

Khai phá tập phổ biến: Áp dụng thuật toán FP-Growth như một bước làm giàu dữ liệu để giải quyết bài toán nhận diện tuyến đường, tạo dữ liệu đầu vào chuẩn xác cho các phân tích cấp cao.

Gom cụm không gian: Ứng dụng thuật toán HDBSCAN dựa trên mật độ để phát hiện và khoanh vùng các điểm đen kẹt xe một cách tự động.

Khai phá chuỗi tuần tự: Sử dụng thuật toán PrefixSpan để tìm ra các quy luật kẹt xe lây lan giữa các khu vực. Bên cạnh đó, đồ án kết hợp kỹ thuật trích xuất chuỗi trạng thái liên tiếp để phân tích hiệu ứng dây chuyền của hiện tượng dồn chuyến giữa các trạm xe buýt.

1. Tiền xử lý dữ liệu

2.1 Tổng quan về bộ dữ liệu

Tập dữ liệu được sử dụng trong đồ án là dữ liệu cấu trúc dạng JSON, ghi nhận lại hành trình GPS của mạng lưới xe buýt tại Thành phố Hồ Chí Minh. Bộ dữ liệu được thu thập liên tục trong 52 ngày (từ 20/03 đến 10/05/2025), bao phủ 31 tuyến xe tiêu biểu với các đặc điểm đa dạng về chiều dài, tần suất và mật độ trạm dừng. Sau khi giải nén, tập dữ liệu gốc có dung lượng khoảng 34GB, chứa hàng chục triệu bản ghi tọa độ theo thời gian thực. Mỗi bản ghi bao gồm các trường thông tin cơ bản như: mã số xe, thời gian, kinh độ, vĩ độ, tốc độ hiện tại, và trạng thái đóng mở của cửa trước và cửa sau.

2.2 Các kỹ thuật tiền xử lý dữ liệu

Do đặc thù dung lượng lớn và chứa nhiều nhiễu từ thiết bị phần cứng, quy trình tiền xử lý được chia thành các bước làm sạch và thu gọn nghiêm ngặt nhằm tối ưu hóa không gian lưu trữ và tốc độ tính toán:

Tích hợp và thu gọn dữ liệu: Dữ liệu thô bao gồm 85 tệp JSON rời rạc được tích hợp thành một tệp định dạng Parquet duy nhất. Quá trình này giúp giảm đáng kể dung lượng lưu trữ và tăng tốc độ đọc dữ liệu lên nhiều lần. Đồng thời, các thuộc tính không mang lại giá trị cho bài toán phân tích giao thông như hướng la bàn, trạng thái điều hòa, cờ đánh dấu xe chở học sinh và trạng thái nổ máy đều được loại bỏ.

Khử trùng lặp và xử lý giá trị khuyết: Các bản ghi bị trùng lặp thời gian phát tín hiệu trên cùng một phương tiện được loại bỏ. Đối với các giá trị khuyết, đồ án áp dụng quy tắc mặc định an toàn: dữ liệu khuyết tốc độ được điền giá trị 0, dữ liệu khuyết trạng thái cửa được mặc định là đóng. Các bản ghi bị mất hoàn toàn thông tin tọa độ sẽ bị xóa bỏ triệt để khỏi tập dữ liệu.

Lọc nhiễu không gian: Để loại bỏ các sai số phần cứng khiến tọa độ GPS bị văng ra khỏi khu vực hoạt động, đồ án thiết lập một ranh giới địa lý bao quanh Thành phố Hồ Chí Minh và các tỉnh lân cận. Mọi tọa độ nằm ngoài ranh giới kinh độ và vĩ độ này đều bị loại trừ.

2.3 Làm giàu dữ liệu và chọn đặc trưng

Sau khi làm sạch, dữ liệu GPS thô được làm giàu thêm các ngữ cảnh về không gian và vận hành để chuẩn bị cho quá trình khai phá:

Ánh xạ trạm bằng thuật toán BallTree: Đây là kỹ thuật cốt lõi để kết nối tọa độ GPS với mạng lưới giao thông. Đồ án xây dựng cấu trúc cây BallTree dựa trên tọa độ của toàn bộ trạm xe buýt và sử dụng công thức Haversine để tính khoảng cách hình cầu. Đối với mỗi điểm GPS, thuật toán sẽ truy vấn trạm gần nhất và gán tên trạm, khoảng cách đến trạm, và cờ đánh dấu bến cuối vào bản ghi. Các điểm GPS cách trạm quá 1000 mét sẽ bị loại bỏ vì không thuộc phạm vi mạng lưới xe buýt.

Nhận diện tuyến đường bằng FP-Growth: Vì nhiều xe buýt đổi tuyến liên tục trong ngày, thuật toán FP-Growth được sử dụng để tìm ra tập phổ biến các trạm mà xe đi qua, từ đó suy luận ngược lại xe đang chạy tuyến nào vào thời điểm đó. Đây là bước làm giàu dữ liệu quan trọng giúp phân cụm điểm đen theo đúng tuyến.

Tạo đặc trưng mới: Dữ liệu được tính toán thêm các thuộc tính mới như tốc độ trung bình giữa hai điểm GPS liên tiếp và phân tách dòng thời gian liên tục thành các chuyến đi riêng biệt thông qua việc gán mã chuyến.

2.4 Phân tích và lựa chọn các tham số nghiệp vụ

Tính chính xác của các mô hình khai phá phụ thuộc lớn vào các tham số ngưỡng được thiết lập dựa trên thực tế vận hành. Các tham số quan trọng nhất được đồ án phân tích và lựa chọn bao gồm:

Hình 1: Phân phối khoảng cách mở cửa so với tâm trạm

Bán kính nhận diện tại trạm: Được thiết lập ở mức 50 mét. Tham số được kết hợp với cờ door_up và door_down để quy định một tín hiệu GPS sẽ được coi là đang dừng tại trạm nếu khoảng cách từ xe đến tâm trạm nhỏ hơn hoặc bằng 50 mét. Tham số này được lựa chọn thông qua việc phân tích phân phối thống kê của các sự kiện mở cửa xe đón khách trên thực tế.

Ngưỡng thời gian phân chuyến: Được thiết lập ở mức 1800 giây. Tham số này quy định nếu một phương tiện mất tín hiệu vượt quá thời gian này, hệ thống sẽ tự động cắt mốc thời gian và tính đây là một chuyến đi mới. Mức thời gian này được chọn vì nó nhỉnh hơn thời lượng hoàn thành của hầu hết các tuyến xe nội đô, phản ánh đúng chu kỳ nghỉ ngơi của tài xế tại bến cuối.

Hình 2: Phân phối thời gian các sự kiện xe buýt dừng liên tục (trên 10 phút)

Ngưỡng thời gian idle (xe dừng liên tục): Được thiết lập ở mức 7200 giây (2 giờ). Để xác định ngưỡng này, đồ án đã phân tích phân phối thời gian của các sự kiện phương tiện không di chuyển liên tục trên 10 phút. Như thể hiện trên biểu đồ, phân phối dữ liệu có dạng đuôi dài, với phần lớn các sự kiện kẹt xe hoặc chờ ca kết thúc trước mốc 4000 giây. Từ mốc 5000 giây trở đi, tần suất sự kiện giảm về mức cực thấp. Để tránh việc thuật toán cắt nhầm các chuyến đi đang chịu kẹt xe nghiêm trọng, đồ án chọn một ngưỡng biên độ an toàn là 7200 giây. Những bản ghi vượt quá mốc thời gian này được phân loại là phương tiện đã ngừng hoạt động kinh doanh (đang sửa chữa hoặc nằm bãi bật máy) và hệ thống sẽ tự động ngắt chuyến đi hiện tại.

1. Phương pháp khai phá dữ liệu

Trong đồ án này, quá trình khai phá dữ liệu được chia làm ba giai đoạn chính, đi từ việc làm giàu dữ liệu đến việc trích xuất tri thức về vận hành. Các thuật toán được lựa chọn đều có sự cân nhắc và đối chiếu với các phương pháp truyền thống nhằm giải quyết đặc thù của dữ liệu không gian - thời gian.

3.1 Nhận diện tuyến đường với thuật toán FP-Growth

Trước khi tiến hành phân tích điểm đen, hệ thống cần biết chính xác mỗi phương tiện đang hoạt động trên tuyến nào. Do đặc thù các xe buýt thường xuyên bị điều động chạy chéo tuyến, đồ án áp dụng kỹ thuật khai phá tập phổ biến thay vì gán nhãn cứng theo lịch trình.

Mô tả thuật toán: Thuật toán FP-Growth được sử dụng để tìm ra các tập hợp trạm xe buýt thường xuyên xuất hiện cùng nhau trong một chuyến đi. Việc lựa chọn FP-Growth thay vì thuật toán Apriori truyền thống xuất phát từ yêu cầu khắt khe về hiệu năng khi xử lý tập dữ liệu lộ trình khổng lồ, cụ thể:

Khắc phục bottleneck sinh tập ứng viên: Khi xử lý hàng chục ngàn chuyến xe và hàng trăm trạm dừng, thuật toán Apriori sẽ tạo ra một tổ hợp các tập ứng viên khổng lồ ở bước nối và tỉa, gây bùng nổ bộ nhớ và tăng thời gian tính toán theo cấp số nhân. Trong khi đó, FP-Growth hoàn toàn loại bỏ bước này nhờ cơ chế chia để trị.

Tối ưu chi phí: Apriori đòi hỏi phải quét toàn bộ cơ sở dữ liệu $k$ lần (với $k$ là độ dài của tập phổ biến lớn nhất). Ngược lại, FP-Growth tỏ ra vượt trội khi nén toàn bộ thông tin vào cấu trúc cây FP-Tree trong bộ nhớ chính, giúp thuật toán chỉ cần quét dữ liệu đúng 2 lần (lần một để đếm tần suất, lần hai để xây cây). Do đó, tốc độ thực thi thực tế của FP-Growth nhanh hơn gấp nhiều lần.

Quy trình và tham số: Mỗi chuyến đi của một xe được xem là một giao dịch, và các trạm xe đi qua là các hạng mục. Thuật toán được thiết lập với tham số $min\_support = 0.6$ (tập trạm phải xuất hiện trong ít nhất 60% số chuyến của một chu kỳ). Dựa trên tập trạm phổ biến nhất tìm được, hệ thống dùng cơ chế bầu chọn theo số đông để đối chiếu với từ điển lộ trình gốc và suy ra mã tuyến thực tế.

3.2 Phân cụm điểm đen giao thông với thuật toán HDBSCAN

Để tự động khoanh vùng các khu vực thường xuyên xảy ra ùn tắc, đồ án áp dụng kỹ thuật phân cụm không gian trên tập các điểm bản ghi GPS thỏa mãn điều kiện kẹt xe (tốc độ di chuyển chậm, cách xa trạm dừng và không mở cửa).

Mô tả thuật toán: Thuật toán HDBSCAN được lựa chọn thay thế cho thuật toán K-Means phổ biến trong đề cương môn học. Việc sử dụng K-Means đối với dữ liệu giao thông gặp hai điểm yếu chí mạng: yêu cầu khai báo trước số lượng cụm (K) và giả định các cụm có hình cầu. Trong thực tế, các điểm kẹt xe thường phân bố kéo dài dọc theo hình dáng đoạn đường và chứa rất nhiều điểm nhiễu cục bộ. HDBSCAN khắc phục hoàn toàn điều này nhờ khả năng tìm ra các cụm có hình dáng bất kỳ dựa trên mật độ và tự động tách biệt các điểm nhiễu ra khỏi kết quả phân tích. Bên cạnh K-Means, thuật toán DBSCAN truyền thống cũng được đồ án đưa ra cân nhắc do có cùng bản chất phân cụm dựa trên mật độ. Xét thuần túy về tốc độ tính toán của máy tính, DBSCAN có thời gian thực thi nhanh hơn HDBSCAN (tùy vào Epsilon) do cơ chế truy vấn lân cận đơn giản hơn. Thế nhưng, điểm yếu chí mạng của DBSCAN là đòi hỏi người dùng phải khai báo trước tham số bán kính giới hạn. Đối với mạng lưới giao thông có mật độ không đồng đều như Thành phố Hồ Chí Minh (khu vực trung tâm các điểm kẹt xe rất dày đặc, trong khi ở ngoại ô lại thưa thớt), việc tìm ra một tham số bán kính duy nhất cho toàn bộ hệ thống là bất khả thi. Việc này dẫn đến việc phải thử nghiệm lại nhiều lần làm tốn kém thời gian tinh chỉnh tổng thể. Do đó, đồ án chấp nhận đánh đổi một chút tốc độ tính toán của HDBSCAN để thuật toán tự động xây dựng cây phân cấp, qua đó thích ứng với các vùng mật độ khác nhau mà không cần tham số bán kính, mang lại chất lượng khoanh vùng điểm đen vượt trội và triệt để hơn.

Quy trình và tham số: Để tối ưu hóa hiệu năng trên tập dữ liệu lớn, tọa độ kinh độ và vĩ độ không dùng trực tiếp hàm Haversine mà được quy đổi sang hệ mét thông qua phép chiếu đẳng cự (equirectangular projection) dựa trên vĩ độ tham chiếu của trung tâm Thành phố Hồ Chí Minh. Việc biến đổi không gian này cho phép thuật toán HDBSCAN sử dụng hàm khoảng cách Euclid, qua đó kích hoạt cấu trúc dữ liệu cây (BallTree) giúp giảm độ phức tạp thời gian xuống mức $O(n \log n)$ và tiết kiệm bộ nhớ tuyến tính $O(n)$. Cách tiếp cận này giải quyết triệt để bài toán tràn RAM so với phương pháp vét cạn $O(n^2)$ của hàm Haversine, trong khi sai số khoảng cách ở phạm vi đô thị là hoàn toàn không đáng kể (dưới 0.1%). Thuật toán được thiết lập tham số $min\_cluster\_size = 50$ mang ý nghĩa nghiệp vụ là cần ít nhất 50 điểm tín hiệu GPS kẹt xe hội tụ mới đủ điều kiện tạo thành một vùng điểm đen. Sau khi loại bỏ các điểm thuộc cụm nhiễu (nhãn -1), tâm chấn của vùng kẹt được tính toán dựa trên tọa độ trung bình của cụm. Cuối cùng, hệ thống áp dụng lại hàm khoảng cách Haversine trên quy mô nhỏ (chỉ dành cho các tâm) để tìm và gán nhãn theo tên trạm xe buýt gần nhất.

3.3 Khai phá chuỗi lây lan kẹt xe với thuật toán PrefixSpan

Không chỉ dừng lại ở việc phát hiện các điểm đen đơn lẻ, đồ án tiến tới việc khai phá tính quy luật của sự lây lan ùn tắc theo thời gian.

Mô tả thuật toán: Để thực hiện việc này, bài toán được mô hình hóa dưới dạng khai phá chuỗi tuần tự. Khác với khai phá tập phổ biến (chỉ quan tâm các phần tử xuất hiện cùng nhau), khai phá tuần tự bảo toàn tính thứ tự trước sau của các sự kiện. Thuật toán PrefixSpan được sử dụng nhờ ưu điểm không cần sinh tập ứng viên khổng lồ mà dùng phương pháp chiếu cơ sở dữ liệu, giúp tiết kiệm tài nguyên bộ nhớ khi phân tích chuỗi không gian.

Quy trình và tham số: Đầu tiên, không gian Thành phố Hồ Chí Minh được rời rạc hóa thành dạng lưới bằng cách làm tròn tọa độ kinh độ và vĩ độ đến 3 chữ số thập phân, tạo thành các định danh khu vực. Các sự kiện kẹt xe của cùng một phương tiện trong ngày được sắp xếp theo thứ tự thời gian tạo thành một chuỗi. Nhóm tiến hành rút gọn các trạng thái trùng lặp liên tiếp để giữ lại chuỗi chuyển dịch cốt lõi. Thuật toán PrefixSpan sau đó được chạy với tham số $min\_support = 20$, nhằm trích xuất ra các chuỗi lây lan kẹt xe đã lặp lại ít nhất 20 lần trong tập dữ liệu lịch sử.

1. Kết quả thực nghiệm và phân tích

4.1 Kết quả phân cụm điểm đen giao thông

Thuật toán HDBSCAN được áp dụng trên tập dữ liệu các điểm sự kiện kẹt xe với tham số kích thước cụm tối thiểu là 50 điểm. Kết quả thực nghiệm cho thấy thuật toán đã phân tách thành công các khu vực kẹt xe lôi ra khỏi các điểm ùn tắc ngẫu nhiên.

Đánh giá hiệu năng thuật toán: Sự ưu việt của HDBSCAN được thể hiện qua khả năng tự động nhận diện và cô lập các điểm nhiễu (những vị trí xe dừng ngẫu nhiên do sự cố cá nhân hoặc đèn đỏ ngắn hạn). Nhờ cơ chế phân cấp mật độ, hệ thống không bị ép phải gom mọi điểm vào một cụm như các thuật toán truyền thống, giúp tâm của các vùng kẹt xe được xác định với độ tin cậy rất cao.

Tri thức khai phá được: Kết quả phân tích cho thấy các điểm đen kẹt xe nghiêm trọng không phân bố ngẫu nhiên mà tuân theo các quy luật không gian rõ rệt. Cụ thể, ách tắc tập trung dày đặc tại các nút giao gần khu vực đông người như công ty, trường học, bệnh viện và ga tàu. Ví dụ điển hình là gần các trạm Ga metro Khu Công nghệ cao, Chợ Long Trường, Đại học Cảnh sát, Bệnh viện Quận Tân Phú,... Bên cạnh đó, kẹt xe cũng bùng phát mạnh trên những cung đường hẹp phải gánh lưu lượng lớn, đặc biệt là tại các ngã ba tiếp nhận dòng phương tiện từ các trục đường chính đổ vào. Đáng chú ý, cấu trúc không gian của nhiều vùng kẹt xe thường kéo dài dọc theo các tuyến đường huyết mạch, phản ánh chính xác đặc tính ách tắc theo dải thay vì chỉ co cụm thành các điểm tĩnh.

4.2 Kết quả phân tích hiện tượng dồn chuyến và thủng tuyến

Quá trình phân tích khoảng cách thời gian giữa các xe trên cùng một tuyến đường đã làm rõ bức tranh về độ tin cậy của dịch vụ. Hệ thống áp dụng ngưỡng dưới 2 phút đối với hiện tượng dồn chuyến và trên 30 phút đối với hiện tượng thủng tuyến (hiện tượng 2 xe cùng 1 tuyến cách nhau quá xa làm người đi xe buýt đợi lâu).

Đánh giá kết quả: Việc sử dụng phương pháp trích xuất chuỗi trạng thái liên tiếp giúp hệ thống lọc bỏ thành công các khoảng nghỉ đêm hợp lệ (trên 180 phút), đảm bảo dữ liệu đầu ra không bị nhiễu bởi thời gian ngừng hoạt động của mạng lưới.

Tri thức khai phá được: Phân phối tần suất lỗi theo khung giờ cho thấy hiện tượng dồn chuyến xảy ra cực kỳ phổ biến vào các khung giờ cao điểm sáng và chiều (7h và 17h). Trái lại, hiện tượng thủng tuyến thường xuất hiện ở các khu vực ngoại ô vào khung giờ thấp điểm (20h) hoặc ngay sau một đợt dồn chuyến kéo dài. Điều này chứng minh sự mất cân bằng về tần suất điều phối tại các trạm dọc đường.

Bảng 2: Tỷ lệ lỗi theo từng giờ trong ngày

Giờ

Tổng sự kiện

Bunching

Gapping

Bottleneck

Bunching %

Gapping %

Bottleneck %

0

1

0

1

0

0.00

100.00

0.00

2

1

0

0

1

0.00

0.00

100.00

3

94

2

0

0

2.13

0.00

0.00

4

4,916

284

156

68

5.78

3.17

1.38

5

22,737

2,478

1,687

197

10.90

7.42

0.87

6

28,730

3,451

2,447

209

12.01

8.52

0.73

7

30,060

3,945

2,691

344

13.12

8.95

1.14

8

28,790

3,551

2,839

299

12.33

9.86

1.04

9

25,128

2,602

2,630

281

10.35

10.47

1.12

10

25,088

2,767

2,937

261

11.03

11.71

1.04

11

26,418

3,205

2,735

297

12.13

10.35

1.12

12

24,529

2,869

2,707

190

11.70

11.04

0.77

13

21,419

2,089

2,820

169

9.75

13.17

0.79

14

20,527

1,968

2,643

180

9.59

12.88

0.88

15

23,925

2,420

2,730

208

10.11

11.41

0.87

16

26,271

3,171

2,625

298

12.07

9.99

1.13

17

26,621

3,629

2,688

429

13.63

10.10

1.61

18

21,509

2,623

2,635

282

12.19

12.25

1.31

19

19,251

2,061

2,963

241

10.71

15.39

1.25

20

10,327

885

1,883

127

8.57

18.23

1.23

21

4,979

587

816

113

11.79

16.39

2.27

22

1,741

202

107

84

11.60

6.15

4.82

23

3

0

0

0

0.00

0.00

0.00

Hình 3: Bảng tỷ lệ bunching/gapping theo từng giờ trong ngày

4.3 Kết quả khai phá chuỗi lây lan điểm đen kẹt xe

Đây là kết quả đột phá của đồ án khi áp dụng thuật toán PrefixSpan để tìm ra các mẫu tuần tự lây lan không gian của hiện tượng kẹt xe. Dữ liệu tọa độ được rời rạc hóa thành các lưới khu vực (Zone ID) và thuật toán được thiết lập với ngưỡng hỗ trợ tối thiểu ($min\_support$) là 20.

Đánh giá hiệu năng: Việc sử dụng PrefixSpan tỏ ra cực kỳ hiệu quả đối với chuỗi dữ liệu không gian - thời gian vì thuật toán này sử dụng phương pháp chiếu cơ sở dữ liệu thay vì sinh tập ứng viên khổng lồ. Tham số $min\_support = 20$ giúp bộ lọc loại bỏ hoàn toàn các chuỗi kẹt xe ngẫu nhiên do tai nạn giao thông cục bộ (chỉ xảy ra một vài lần), giữ lại những luồng ách tắc mang tính chu kỳ và có tính quy luật hạ tầng rõ rệt.

Tri thức khai phá được: Kết quả đã bóc tách được các luồng lây lan kẹt xe nghiêm trọng (hiệu ứng domino không gian). Các chuỗi phổ biến cho thấy hướng di chuyển của dòng kẹt xe thường bắt nguồn từ các cửa ngõ bến xe lớn (ví dụ: Bến xe An Sương, Bến xe buýt Phổ Quang...) và có xu hướng lây lan ngược chiều dòng xe cộ về phía các ngã tư trung tâm kề cận vào khung giờ cao điểm.

4.4 Kết quả phân tích chuỗi hiệu ứng dây chuyền vận hành

Bên cạnh kẹt xe vật lý, hệ thống còn trích xuất thành công các chuỗi lây lan lỗi vận hành (hiệu ứng domino nghiệp vụ) bằng kỹ thuật phân tích chuỗi trạng thái liên tiếp. Hệ thống khoanh vùng các sự kiện lỗi kéo dài qua ít nhất 2 trạm liên tiếp và đã lặp lại từ 3 lần trở lên trong lịch sử.

Đánh giá hiệu năng: Thuật toán chặn đứng các chuỗi lây lan ngay khi phát hiện phương tiện chuyển sang trạng thái bình thường (Normal), đổi chuyến hoặc đổi xe. Điều này giúp đảm bảo các quy tắc lây lan khai phá được phản ánh đúng một chuỗi nhân quả duy nhất, không bị nhiễu bởi các khoảng nghỉ hợp lệ của tài xế.

Tri thức khai phá được: Dữ liệu chỉ ra quy luật vận hành rõ nét: khi một trạm trung tâm bị nghẽn (Bottleneck) kéo dài quá 3 phút, nó lập tức gây ra hiện tượng thiếu xe (Gapping) ở 2 đến 3 trạm tiếp theo trên cùng một lộ trình. Khi trạm trung tâm được giải tỏa, một đàn 2-3 chiếc xe bị dồn ở trạm trung tâm cùng lúc ùa tới, sinh ra hiện tượng dồn chuyến (Bunching).

4.5 Đánh giá mức độ đáp ứng mục tiêu

Đối chiếu với bài toán đặt ra ở phần mở đầu, các kết quả thực nghiệm chứng minh hệ thống đã giải quyết trọn vẹn vấn đề hộp đen trong công tác vận hành. Thay vì chỉ giám sát tọa độ rời rạc, hệ thống đã thành công trong việc trích xuất các quy luật ẩn về điểm đen, dồn chuyến và chuỗi lây lan. Những tri thức này hoàn toàn có thể hành động được, đóng vai trò như một hệ thống cảnh báo sớm giúp ban điều phối giao thông đưa ra các quyết định can thiệp kịp thời.

1. Trình diễn tri thức và ứng dụng

5.1 Xây dựng hệ thống bảng điều khiển tương tác

Thay vì chỉ in ra các con số rời rạc, đồ án đã phát triển một ứng dụng web đa trang sử dụng framework Streamlit. Hệ thống được thiết kế theo nguyên lý từ tổng quan đến chi tiết, cung cấp cho người quản lý một trung tâm chỉ huy số hóa. Tại đây, luồng dữ liệu khai phá được nạp trực tiếp vào giao diện, đảm bảo tính liền mạch giữa phân tích và trình diễn.

5.2 Trực quan hóa kết quả khai phá

Bản đồ không gian ba chiều: Trình diễn kết quả phân cụm HDBSCAN. Hệ thống sử dụng các cột lục giác để biểu diễn mật độ kẹt xe, kết hợp với các tâm chấn để người dùng dễ dàng nhận diện điểm nóng giao thông trên bản đồ thành phố.

Bản đồ luồng lây lan: Trình diễn kết quả của thuật toán PrefixSpan. Ứng dụng vẽ các đường vòng cung nối liền các trạm, giúp người xem hình dung rõ ràng hướng di chuyển và cường độ của hiệu ứng dây chuyền.

Ma trận nhiệt và biểu đồ phân phối: Trình diễn kết quả phân tích hiện tượng dồn chuyến. Các ô màu nóng lạnh giúp phát hiện nhanh chóng khung giờ và trạm xe nào đang có nguy cơ thủng tuyến cao nhất.

5.3 Ứng dụng hỗ trợ ra quyết định (kịch bản thực tế)

Để minh chứng cho giá trị thực tiễn của đồ án, nhóm nghiên cứu xây dựng một kịch bản nghiệp vụ tiêu biểu: Đánh giá toàn diện nguyên nhân suy giảm chất lượng dịch vụ của một tuyến xe buýt trọng điểm và đưa ra phương án khắc phục.

5.3.1 Bước 1: Nhận diện tuyến có hiệu suất kém từ màn hình tổng quan

Người quản lý bắt đầu phiên làm việc tại trang Dashboard.py. Màn hình KPI (tầng 1) báo động đỏ khi chỉ số vận hành tổng thể giảm xuống dưới mức mục tiêu (service_health_target_pct). Để xác định thủ phạm, người quản lý cuộn xuống tầng 3, mở tab Bảng xếp hạng các tuyến. Hệ thống tự động tính toán điểm Bad Score bằng cách cộng gộp tỷ lệ phần trăm các lỗi Bottleneck, Bunching, và Gapping. Tuyến xe buýt số 91 bị đẩy lên đầu bảng với màu đỏ sậm nhất (gradient Reds), cho thấy đây là tuyến đang gặp vấn đề nghiêm trọng nhất mạng lưới (tại đây chọn tuyến 91 do có dữ liệu nhiều).

Hình 4: Dashboard điều hành

Hình 5: Bảng xếp hạng chi tiết các tuyến

5.3.2 Bước 2: Phân tích không gian và thời gian của lỗi Bunching/Gapping

Để tìm hiểu xem Tuyến 91 bị lỗi ở đâu và khi nào, người quản lý chuyển sang trang 3_Transit Performance.py và dùng bộ lọc trên sidebar để cô lập dữ liệu riêng của Tuyến 91 chiều Outbound. Tại tab Bản đồ nhiệt (Bunching & Gapping), ma trận phân phối hiện ra rõ rệt:

Ở biểu đồ Bunching (Reds), một vệt màu đỏ rực xuất hiện tại nhóm trạm "Lăng Ông Bà Chiểu" và "UBND Quận Bình Thạnh" tập trung vào khung giờ 07:00 đến 08:00 sáng. Điều này chứng tỏ các xe liên tục dồn cục vào nhau tại đây.

Ngay bên cạnh, biểu đồ Gapping (Blues) hiển thị vệt xanh đậm ở các trạm trước đó là ("Công Viên Lê Văn Tám", "Dinh Tiên Hoàng") từ 08:30 trở đi.

Hệ thống đã vẽ lên một câu chuyện rõ ràng: Ách tắc tại khu vực trung tâm vào đầu giờ sáng đã bóp méo biểu đồ chạy xe, dẫn đến tình trạng thủng tuyến nghiêm trọng ở nửa sau của lộ trình.

Hình 6: Tìm kiếm nguyên nhân làm giảm kpi của tuyến

5.3.3 Bước 3: Xác thực nguyên nhân vật lý bằng bản đồ điểm đen 3D

Liệu hiện tượng dồn chuyến này do lỗi điều độ hay do kẹt xe khách quan? Người quản lý mở trang 2_Black Spot.py để kiểm chứng. Khi lọc Tuyến 91 và khung giờ 07:00-08:00, bản đồ 3D kết xuất các cột Hexagon Layer cao vút tại chính khu vực Đền Trần Hưng Đạo (nằm giữa Công viên Lê Văn Tám và Lăng Ông Bà Chiểu). Thuật toán HDBSCAN khoanh vùng khu vực này bằng một tâm chấn đỏ rực với chỉ số Severity rất cao. Người quản lý nhấp chuột vào bảng báo cáo điểm đen, ngay lập tức zoom vào trạm này. Kết luận: Đây là điểm đen kẹt xe mang tính hệ thống do hạ tầng giao thông, không phải do lỗi chủ quan của tài xế.

Hình 7: 1. Gapping, 2. Kẹt xe, 3. Bunching

5.3.4 Bước 4: Đánh giá phản ứng của tài xế trước sự cố

Khi bị kẹt xe kéo dài, tài xế thường có xu hướng vi phạm quy tắc. Người quản lý quay lại Dashboard.py, mở tab Bảng đánh giá hành vi tài xế và lọc theo Tuyến 91. Các bussiness rule của hệ thống ngay lập tức lấy các hồ sơ xấu. Rất nhiều tài xế của Tuyến 91 bị gán nhãn Violator (tỷ lệ mở cửa cách xa tâm trạm trên 50 mét vượt quá ngưỡng 60%). Dữ liệu chỉ ra rằng: do kẹt cứng tại Đền Trần Hưng Đạo, tài xế đã tự ý mở cửa giữa đường để sinh viên xuống xe đi bộ cho kịp giờ học. Một số tài xế khác bị gán nhãn Reckless do có độ dao động vận tốc (speed_std) quá cao khi cố gắng tăng tốc bù giờ sau khi thoát khỏi điểm kẹt.

5.3.5 Ra quyết định điều hành

Dựa trên chuỗi tri thức liền mạch từ hệ thống, ban quản lý không đánh giá cảm tính mà đưa ra các quyết định dựa trên dữ liệu:

Giải pháp ngắn hạn: Nhờ biết được quy luật từ tab Lây lan domino (PrefixSpan), khi trạm Ngã tư Chu Văn An bắt đầu chớm nghẽn, tổng đài tự động ra lệnh cho các xe chuẩn bị tới trạm Đền Trần Hưng Đạo giảm tốc hay tăng tốc dựa theo lưu lượng lưu thông để tránh kẹt xe tại Trạm Đền Trần Hưng Đạo.

Hình 8: Hiệu ứng Domino (Lưu ý: Chú thích ảnh theo nội dung bản đồ)

Quản lý nhân sự: Không phạt nặng các tài xế Violator bị kẹt tại Đền Trần Hưng Đạo vì đây là tình thế ép buộc, nhưng sẽ gửi cảnh báo yêu cầu các tài xế Reckless giảm thói quen lái xe ẩu để đảm bảo an toàn.

Giải pháp dài hạn: Kiến nghị Sở GTVT điều chỉnh biểu đồ giờ của Tuyến 91, nới lỏng thời gian di chuyển qua phân đoạn Đền Trần Hưng Đạo vào buổi sáng, hoặc dời vị trí trạm dừng ra xa nút giao thêm 100 mét để xe buýt không bị kẹt chung với dòng xe máy.

1. Tổng kết và hướng phát triển tương lai

6.1 Tổng kết những đóng góp của đồ án

Đồ án đã hoàn thành mục tiêu đặt ra từ đầu là giải quyết bài toán hộp đen trong công tác quản lý và vận hành mạng lưới xe buýt tại Thành phố Hồ Chí Minh. Nhóm nghiên cứu đã xây dựng thành công một đường ống dữ liệu hoàn chỉnh, xử lý hiệu quả khối lượng lớn dữ liệu GPS thô và áp dụng linh hoạt các thuật toán khai phá dữ liệu tiên tiến.

Cụ thể, việc áp dụng thuật toán FP-Growth đã giải quyết triệt để bài toán nhận diện tuyến đường động cho các phương tiện. Thuật toán HDBSCAN chứng minh được sự ưu việt trong việc tự động khoanh vùng các điểm đen kẹt xe và loại bỏ điểm nhiễu. Đặc biệt, thuật toán PrefixSpan cùng kỹ thuật phân tích chuỗi trạng thái đã bóc tách thành công các quy luật lây lan hiệu ứng domino trong không gian và hiện tượng dồn chuyến theo thời gian. Toàn bộ tri thức khai phá được đã được đóng gói thành một hệ thống bảng điều khiển tương tác, cung cấp công cụ hỗ trợ ra quyết định trực quan và đắc lực cho cấp quản lý vận hành.

6.2 Hạn chế của đồ án

Mặc dù đạt được những kết quả mang tính thực tiễn cao, đồ án vẫn còn tồn tại một số giới hạn nhất định:

Về quy mô dữ liệu: Hệ thống hiện tại chỉ mới tiến hành khai phá trên tập dữ liệu mẫu gồm 31 tuyến xe buýt trong phạm vi 50 ngày. Mặc dù đây là các tuyến trọng điểm, việc chưa bao quát toàn bộ mạng lưới giao thông của thành phố khiến cho một số chuỗi lây lan ách tắc diện rộng xuyên tuyến có thể chưa được khám phá trọn vẹn.

Về thuật toán nhận diện: Thuật toán nhận diện tuyến đường dựa trên tập phổ biến có thể bị giảm độ chính xác trong các tình huống cực đoan, ví dụ như khi phương tiện phải đi chệch hoàn toàn khỏi lộ trình gốc do đường bị phong tỏa hoặc ngập nước mà hệ thống chưa kịp cập nhật từ điển trạm.

Về kiến trúc xử lý: Các quy trình tiền xử lý và khai phá hiện tại đang hoạt động theo mô hình batch process. Điều này rất tốt cho việc phân tích dữ liệu lịch sử nhưng chưa đáp ứng được yêu cầu phân tích luồng dữ liệu thời gian thực để đưa ra cảnh báo tức thời tính bằng giây.

6.3 Hướng phát triển tương lai

Dựa trên những nền tảng vững chắc đã xây dựng và các hạn chế còn tồn đọng, đồ án đề xuất các hướng phát triển tiếp theo như sau:

Tích hợp dữ liệu đa nguồn: Mở rộng không gian đặc trưng bằng cách thu thập và tích hợp thêm các nguồn dữ liệu ngoại cảnh như tình hình thời tiết, lịch sự kiện lễ hội, hoặc dữ liệu từ hệ thống camera giao thông. Việc làm giàu dữ liệu này sẽ giúp giải thích sâu hơn nguyên nhân gốc rễ của các điểm đen kẹt xe ngẫu nhiên.

Nâng cấp kiến trúc luồng dữ liệu: Chuyển đổi hệ thống từ xử lý lô sang kiến trúc xử lý luồng thời gian thực sử dụng các công nghệ dữ liệu lớn tiên tiến. Điều này sẽ cho phép bảng điều khiển cập nhật trạng thái dồn chuyến và thủng tuyến ngay lập tức khi xe đang chạy trên đường.

Ứng dụng mô hình dự báo: Những tri thức và quy luật lây lan khai phá được từ đồ án này là nguồn nguyên liệu chất lượng cao để tiến tới xây dựng các mô hình học máy. Mục tiêu tương lai là dự báo chính xác thời gian hành trình và đưa ra cảnh báo về nguy cơ ùn tắc hoặc thủng tuyến trước khi chúng thực sự xảy ra.

Tài liệu tham khảo

[1] Khang Nguyen Duy and Nam Thoai. Ho chi minh city bus gps dataset. Kaggle Dataset, 2025. Truy cập ngày 6 tháng 4 năm 2026.

[2] Chuancong Gao. prefixspan pypi. <https://pypi.org/project/prefixspan/>. Truy cập ngày 8 tháng 4 năm 2026.

[3] Leland McInnes, John Healy, and Steve Astels. hdbscan: Hierarchical density based clustering. The Journal of Open Source Software, 2(11):205, 2017.

[4] Sebastian Raschka. Mlxtend: Providing machine learning and data science utilities and extensions to python's scientific computing stack. The Journal of Open Source Software, 3(24):638, 2018.

[5] Wikipedia contributors. Bus bunching. <https://en.wikipedia.org/wiki/Bus_bunching>. Truy cập ngày 6 tháng 4 năm 2026.
