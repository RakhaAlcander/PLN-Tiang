import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Calculator, FileText, Download, Upload, File } from 'lucide-react';
import * as XLSX from 'xlsx';

const SistemRABTiangListrik = () => {
  const [tiang, setTiang] = useState([]);
  const [tiangAwal, setTiangAwal] = useState('TM1');
  const [hargaMaterial, setHargaMaterial] = useState({
    TM1: { material: 5000000, tukang: 500000, alat: 200000 },
    TM2: { material: 7500000, tukang: 750000, alat: 300000 },
    TM10: { material: 12000000, tukang: 1200000, alat: 500000 },
    TM4: { material: 8000000, tukang: 800000, alat: 350000 }
  });
  
  const [inputSudut, setInputSudut] = useState('');
  const [klasifikasi, setKlasifikasi] = useState({});
  const [totalRAB, setTotalRAB] = useState({});
  const [isLoadingExcel, setIsLoadingExcel] = useState(false);
  const [excelInfo, setExcelInfo] = useState({ tiang: null, harga: null });

  // Fungsi klasifikasi tiang berdasarkan sudut
  const klasifikasiTiang = (sudut) => {
    if (sudut <= 15) return 'TM1';
    if (sudut >= 16 && sudut <= 45) return 'TM2';
    if (sudut >= 46) return 'TM10';
    return 'TM1';
  };

  // Fungsi untuk membaca Excel - Data Tiang
  const handleExcelTiang = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsLoadingExcel(true);
    try {
      const data = await file.arrayBuffer();
      const workbook = XLSX.read(data);
      const worksheet = workbook.Sheets[workbook.SheetNames[0]];
      const jsonData = XLSX.utils.sheet_to_json(worksheet);

      // Proses data Excel dengan format: Latitude,Longitude,Label,Sudut (derajat),Kategori
      const tiangFromExcel = jsonData.map((row, index) => {
        // Ambil sudut dari kolom "Sudut (derajat)" atau variasi nama lainnya
        const sudut = parseFloat(
          row["Sudut (derajat)"] || 
          row["Sudut"] || 
          row["sudut"] || 
          row["SUDUT"] || 
          row["Sudut (Derajat)"] ||
          row["SUDUT (DERAJAT)"] || 0
        );
        
        // Ambil kategori asli dari Excel (jika ada)
        const kategoriAsli = row["Kategori"] || row["kategori"] || row["KATEGORI"];
        
        return {
          id: Date.now() + index,
          latitude: row["Latitude"] || row["latitude"] || row["LATITUDE"] || "",
          longitude: row["Longitude"] || row["longitude"] || row["LONGITUDE"] || "",
          label: row["Label"] || row["label"] || row["LABEL"] || `Tiang ${index + 1}`,
          sudut: sudut,
          kategoriAsli: kategoriAsli,
          kategori: klasifikasiTiang(sudut), // Klasifikasi berdasarkan sudut
          posisi: index === 0 ? 'awal' : 'tengah',
          nama: row["Label"] || row["label"] || row["LABEL"] || `Tiang ${index + 1}`
        };
      });

      setTiang(tiangFromExcel);
      setExcelInfo(prev => ({ ...prev, tiang: file.name }));
      alert(`Berhasil import ${tiangFromExcel.length} data tiang dari Excel!`);
    } catch (error) {
      alert('Error membaca file Excel: ' + error.message);
    }
    setIsLoadingExcel(false);
  };

  // Fungsi untuk membaca Excel - Data Harga
  const handleExcelHarga = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsLoadingExcel(true);
    try {
      const data = await file.arrayBuffer();
      const workbook = XLSX.read(data);
      const worksheet = workbook.Sheets[workbook.SheetNames[0]];
      const jsonData = XLSX.utils.sheet_to_json(worksheet);

      // Proses data Excel dengan format: NO, MVTIC SAT, URAIAN, HARGA SATUAN, PSG TUNAI PLN, MATERIAL, PASANG
      const hargaFromExcel = {};
      
      jsonData.forEach(row => {
        // Ambil uraian untuk menentukan kategori tiang
        const uraian = (row["URAIAN"] || row["Uraian"] || row["uraian"] || "").toString().toUpperCase();
        
        // Identifikasi kategori berdasarkan uraian
        let kategori = null;
        if (uraian.includes("TM1") || uraian.includes("TM 1")) kategori = "TM1";
        else if (uraian.includes("TM2") || uraian.includes("TM 2")) kategori = "TM2";
        else if (uraian.includes("TM10") || uraian.includes("TM 10")) kategori = "TM10";
        else if (uraian.includes("TM4") || uraian.includes("TM 4")) kategori = "TM4";
        
        if (kategori) {
          // Ambil harga dari kolom yang sesuai
          const hargaSatuan = parseFloat(row["HARGA SATUAN"] || row["Harga Satuan"] || row["harga satuan"] || 0);
          const psgTunai = parseFloat(row["PSG TUNAI PLN"] || row["Psg Tunai PLN"] || row["psg tunai pln"] || 0);
          const material = parseFloat(row["MATERIAL"] || row["Material"] || row["material"] || 0);
          const pasang = parseFloat(row["PASANG"] || row["Pasang"] || row["pasang"] || 0);
          
          // Inisialisasi kategori jika belum ada
          if (!hargaFromExcel[kategori]) {
            hargaFromExcel[kategori] = { material: 0, tukang: 0, alat: 0 };
          }
          
          // Set harga berdasarkan prioritas kolom
          if (material > 0) {
            hargaFromExcel[kategori].material = material;
          } else if (hargaSatuan > 0) {
            hargaFromExcel[kategori].material = hargaSatuan;
          }
          
          if (pasang > 0) {
            hargaFromExcel[kategori].tukang = pasang;
          } else if (psgTunai > 0) {
            hargaFromExcel[kategori].tukang = psgTunai;
          }
          
          // Untuk alat, gunakan persentase dari material (estimasi 10%)
          if (hargaFromExcel[kategori].material > 0) {
            hargaFromExcel[kategori].alat = Math.round(hargaFromExcel[kategori].material * 0.1);
          }
        }
      });

      if (Object.keys(hargaFromExcel).length > 0) {
        setHargaMaterial(prev => ({ ...prev, ...hargaFromExcel }));
        setExcelInfo(prev => ({ ...prev, harga: file.name }));
        alert(`Berhasil import data harga untuk ${Object.keys(hargaFromExcel).length} kategori!`);
      } else {
        alert('Tidak ada data harga yang valid ditemukan. Pastikan kolom URAIAN mengandung TM1, TM2, TM10, atau TM4.');
      }
    } catch (error) {
      alert('Error membaca file Excel: ' + error.message);
    }
    setIsLoadingExcel(false);
  };

  // Export ke Excel
  const exportToExcel = () => {
    // Create workbook
    const wb = XLSX.utils.book_new();

    // Sheet 1: Data Tiang
    const tiangData = tiang.map((t, index) => ({
      No: index + 1,
      Latitude: t.latitude || '',
      Longitude: t.longitude || '',
      Label: t.nama || `Tiang ${index + 1}`,
      'Sudut (derajat)': t.sudut,
      Kategori_Asli: t.kategoriAsli || '',
      Kategori_Berdasarkan_Sudut: t.kategori,
      Kategori_Final: t.posisi === 'awal' ? tiangAwal : t.posisi === 'akhir' ? 'TM4' : t.kategori,
      Posisi: t.posisi
    }));
    const ws1 = XLSX.utils.json_to_sheet(tiangData);
    XLSX.utils.book_append_sheet(wb, ws1, "Data Tiang");

    // Sheet 2: Klasifikasi
    const klasifikasiData = Object.entries(klasifikasi).map(([kategori, jumlah]) => ({
      Kategori: kategori,
      Jumlah: jumlah
    }));
    const ws2 = XLSX.utils.json_to_sheet(klasifikasiData);
    XLSX.utils.book_append_sheet(wb, ws2, "Klasifikasi");

    // Sheet 3: RAB
    const rabData = Object.entries(totalRAB).map(([kategori, data]) => ({
      Kategori: kategori,
      Jumlah: data.jumlah,
      Material: data.material,
      Tukang: data.tukang,
      Alat: data.alat,
      Total: data.total
    }));
    // Add grand total row
    rabData.push({
      Kategori: 'GRAND TOTAL',
      Jumlah: '',
      Material: '',
      Tukang: '',
      Alat: '',
      Total: grandTotal
    });
    const ws3 = XLSX.utils.json_to_sheet(rabData);
    XLSX.utils.book_append_sheet(wb, ws3, "RAB");

    // Sheet 4: Database Harga
    const hargaData = Object.entries(hargaMaterial).map(([kategori, harga]) => ({
      Kategori: kategori,
      Material: harga.material,
      Tukang: harga.tukang,
      Alat: harga.alat
    }));
    const ws4 = XLSX.utils.json_to_sheet(hargaData);
    XLSX.utils.book_append_sheet(wb, ws4, "Database Harga");

    // Save file
    const fileName = `RAB_Tiang_Listrik_${new Date().toISOString().split('T')[0]}.xlsx`;
    XLSX.writeFile(wb, fileName);
  };
  const tambahTiang = () => {
    if (!inputSudut) return;
    
    const sudut = parseFloat(inputSudut);
    const kategori = klasifikasiTiang(sudut);
    
    const tiangBaru = {
      id: Date.now(),
      sudut: sudut,
      kategori: kategori,
      posisi: tiang.length === 0 ? 'awal' : 'tengah'
    };
    
    setTiang(prev => [...prev, tiangBaru]);
    setInputSudut('');
  };

  // Hapus tiang
  const hapusTiang = (id) => {
    setTiang(prev => prev.filter(t => t.id !== id));
  };

  // Update klasifikasi dan hitung RAB
  useEffect(() => {
    if (tiang.length === 0) {
      setKlasifikasi({});
      setTotalRAB({});
      return;
    }

    // Update posisi tiang
    const tiangUpdated = tiang.map((t, index) => ({
      ...t,
      posisi: index === 0 ? 'awal' : index === tiang.length - 1 ? 'akhir' : 'tengah'
    }));

    // Set kategori tiang awal dan akhir
    const tiangFinal = tiangUpdated.map(t => ({
      ...t,
      kategori: t.posisi === 'awal' ? tiangAwal : t.posisi === 'akhir' ? 'TM4' : t.kategori
    }));

    // Hitung klasifikasi
    const klasifikasiCount = tiangFinal.reduce((acc, t) => {
      acc[t.kategori] = (acc[t.kategori] || 0) + 1;
      return acc;
    }, {});

    // Hitung RAB
    const rabTotal = Object.entries(klasifikasiCount).reduce((acc, [kategori, jumlah]) => {
      const harga = hargaMaterial[kategori];
      acc[kategori] = {
        jumlah: jumlah,
        material: harga.material * jumlah,
        tukang: harga.tukang * jumlah,
        alat: harga.alat * jumlah,
        total: (harga.material + harga.tukang + harga.alat) * jumlah
      };
      return acc;
    }, {});

    setKlasifikasi(klasifikasiCount);
    setTotalRAB(rabTotal);
  }, [tiang, tiangAwal, hargaMaterial]);

  // Format currency
  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0
    }).format(amount);
  };

  // Hitung grand total
  const grandTotal = Object.values(totalRAB).reduce((sum, item) => sum + item.total, 0);

  // Update harga material
  const updateHarga = (kategori, jenis, nilai) => {
    setHargaMaterial(prev => ({
      ...prev,
      [kategori]: {
        ...prev[kategori],
        [jenis]: parseFloat(nilai) || 0
      }
    }));
  };

  return (
    <div className="max-w-7xl mx-auto p-6 bg-gray-50 min-h-screen">
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <h1 className="text-3xl font-bold text-gray-800 mb-2 flex items-center">
          <FileText className="mr-3 text-blue-600" />
          Sistem RAB Tiang Listrik Otomatis
        </h1>
        <p className="text-gray-600">Klasifikasi otomatis tiang listrik dan perhitungan RAB terintegrasi</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Import Excel Section */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800 flex items-center">
            <Upload className="mr-2" />
            Import Data Excel
          </h2>
          
          {/* Import Data Tiang */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Import Data Tiang dari Excel
            </label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 hover:border-blue-500 transition-colors">
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={handleExcelTiang}
                className="hidden"
                id="excel-tiang"
                disabled={isLoadingExcel}
              />
              <label
                htmlFor="excel-tiang"
                className="cursor-pointer flex flex-col items-center justify-center"
              >
                <File className="w-8 h-8 text-gray-400 mb-2" />
                <span className="text-sm text-gray-600">
                  {isLoadingExcel ? 'Memproses...' : 'Klik untuk upload file Excel data tiang'}
                </span>
                {excelInfo.tiang && (
                  <span className="text-xs text-green-600 mt-1">
                    ✓ {excelInfo.tiang}
                  </span>
                )}
              </label>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              <p>Format Excel yang diharapkan:</p>
              <p>• Kolom: Latitude, Longitude, Label, Sudut (derajat), Kategori</p>
              <p>• Contoh: Latitude=-6.123, Longitude=106.456, Label="Tiang A1", Sudut (derajat)=20</p>
            </div>
          </div>

          {/* Import Data Harga */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Import Database Harga dari Excel
            </label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 hover:border-blue-500 transition-colors">
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={handleExcelHarga}
                className="hidden"
                id="excel-harga"
                disabled={isLoadingExcel}
              />
              <label
                htmlFor="excel-harga"
                className="cursor-pointer flex flex-col items-center justify-center"
              >
                <File className="w-8 h-8 text-gray-400 mb-2" />
                <span className="text-sm text-gray-600">
                  {isLoadingExcel ? 'Memproses...' : 'Klik untuk upload file Excel database harga'}
                </span>
                {excelInfo.harga && (
                  <span className="text-xs text-green-600 mt-1">
                    ✓ {excelInfo.harga}
                  </span>
                )}
              </label>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              <p>Format Excel yang diharapkan:</p>
              <p>• Kolom: NO, MVTIC SAT, URAIAN, HARGA SATUAN, PSG TUNAI PLN, MATERIAL, PASANG</p>
              <p>• URAIAN harus mengandung: TM1, TM2, TM10, atau TM4</p>
              <p>• Contoh URAIAN: "Tiang Beton TM1 12m", "Konstruksi TM2 Sudut"</p>
            </div>
          </div>
        </div>

        {/* Input Section */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">Input Manual Data Tiang</h2>
          
          {/* Tiang Awal Selection */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kategori Tiang Awal (By Request)
            </label>
            <select 
              value={tiangAwal} 
              onChange={(e) => setTiangAwal(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="TM1">TM1</option>
              <option value="TM2">TM2</option>
              <option value="TM10">TM10</option>
              <option value="TM4">TM4</option>
            </select>
          </div>

          {/* Input Sudut */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Sudut Kemiringan (°)
            </label>
            <div className="flex gap-2">
              <input
                type="number"
                value={inputSudut}
                onChange={(e) => setInputSudut(e.target.value)}
                placeholder="Masukkan sudut kemiringan"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={tambahTiang}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center"
              >
                <Plus className="w-4 h-4 mr-1" />
                Tambah
              </button>
            </div>
          </div>

          {/* Kriteria Klasifikasi */}
          <div className="bg-blue-50 p-4 rounded-lg mb-4">
            <h3 className="font-semibold text-blue-800 mb-2">Kriteria Klasifikasi:</h3>
            <ul className="text-sm text-blue-700 space-y-1">
              <li>• TM1: ≤ 15°</li>
              <li>• TM2: 16° - 45°</li>
              <li>• TM10: ≥ 46°</li>
              <li>• TM4: Tiang Akhir (Otomatis)</li>
            </ul>
          </div>

          {/* Daftar Tiang */}
          <div className="max-h-60 overflow-y-auto">
            <h3 className="font-semibold mb-2">Daftar Tiang ({tiang.length})</h3>
            {tiang.length === 0 ? (
              <p className="text-gray-500 text-center py-4">Belum ada tiang yang ditambahkan</p>
            ) : (
              <div className="space-y-2">
                {tiang.map((t, index) => (
                  <div key={t.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex-1">
                      <span className="font-medium">
                        {t.nama || t.label || `Tiang ${index + 1}`} ({t.posisi === 'awal' ? tiangAwal : t.posisi === 'akhir' ? 'TM4' : t.kategori})
                      </span>
                      <div className="text-sm text-gray-600">
                        Sudut: {t.sudut}° | Posisi: {t.posisi}
                        {t.latitude && t.longitude && (
                          <div>Koordinat: {t.latitude}, {t.longitude}</div>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => hapusTiang(t.id)}
                      className="p-1 text-red-600 hover:bg-red-100 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Hasil Klasifikasi */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800 flex items-center">
            <Calculator className="mr-2" />
            Hasil Klasifikasi
          </h2>
          
          {Object.keys(klasifikasi).length === 0 ? (
            <p className="text-gray-500 text-center py-8">Tambahkan tiang untuk melihat hasil klasifikasi</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(klasifikasi).map(([kategori, jumlah]) => (
                <div key={kategori} className="flex justify-between items-center p-3 bg-green-50 rounded-lg">
                  <span className="font-medium text-green-800">{kategori}</span>
                  <span className="bg-green-200 text-green-800 px-3 py-1 rounded-full text-sm font-semibold">
                    {jumlah} unit
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Database Harga */}
      <div className="bg-white rounded-lg shadow-lg p-6 mt-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-800">Database Harga Material & Tenaga Kerja</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(hargaMaterial).map(([kategori, harga]) => (
            <div key={kategori} className="border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold text-center mb-3 text-blue-600">{kategori}</h3>
              <div className="space-y-2">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Material</label>
                  <input
                    type="number"
                    value={harga.material}
                    onChange={(e) => updateHarga(kategori, 'material', e.target.value)}
                    className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Tukang</label>
                  <input
                    type="number"
                    value={harga.tukang}
                    onChange={(e) => updateHarga(kategori, 'tukang', e.target.value)}
                    className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Alat</label>
                  <input
                    type="number"
                    value={harga.alat}
                    onChange={(e) => updateHarga(kategori, 'alat', e.target.value)}
                    className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* RAB Calculation */}
      {Object.keys(totalRAB).length > 0 && (
        <div className="bg-white rounded-lg shadow-lg p-6 mt-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">Rencana Anggaran Biaya (RAB)</h2>
          
          <div className="overflow-x-auto">
            <table className="w-full border-collapse border border-gray-300">
              <thead className="bg-blue-600 text-white">
                <tr>
                  <th className="border border-gray-300 px-4 py-2">Kategori</th>
                  <th className="border border-gray-300 px-4 py-2">Jumlah</th>
                  <th className="border border-gray-300 px-4 py-2">Material</th>
                  <th className="border border-gray-300 px-4 py-2">Tukang</th>
                  <th className="border border-gray-300 px-4 py-2">Alat</th>
                  <th className="border border-gray-300 px-4 py-2">Total</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(totalRAB).map(([kategori, data]) => (
                  <tr key={kategori} className="even:bg-gray-50">
                    <td className="border border-gray-300 px-4 py-2 font-medium">{kategori}</td>
                    <td className="border border-gray-300 px-4 py-2 text-center">{data.jumlah}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right">{formatCurrency(data.material)}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right">{formatCurrency(data.tukang)}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right">{formatCurrency(data.alat)}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right font-semibold">{formatCurrency(data.total)}</td>
                  </tr>
                ))}
                <tr className="bg-blue-100 font-bold">
                  <td colSpan="5" className="border border-gray-300 px-4 py-2 text-right">GRAND TOTAL:</td>
                  <td className="border border-gray-300 px-4 py-2 text-right text-blue-800">{formatCurrency(grandTotal)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex justify-end space-x-3">
            <button 
              onClick={exportToExcel}
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center"
            >
              <Download className="w-4 h-4 mr-2" />
              Export Excel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SistemRABTiangListrik;