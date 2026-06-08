package com.mercadez.dto;

import com.mercadez.model.Afiliado;
import lombok.Data;
import java.time.LocalDateTime;

@Data
public class AfiliadoResponse {
    private Long          id;
    private String        nome_proprietario;   // snake_case para o frontend
    private String        email;
    private String        cnpj;
    private String        endereco;
    private String        telefone;
    private String        mercado;
    private String        categoria;
    private Integer       funcionarios;
    private String        pagamento;
    private Boolean       ativo;
    private LocalDateTime criadoEm;

    public static AfiliadoResponse de(Afiliado a) {
        var r = new AfiliadoResponse();
        r.setId(a.getId());
        r.setNome_proprietario(a.getNomeProprietario());
        r.setEmail(a.getEmail());
        r.setCnpj(a.getCnpj());
        r.setEndereco(a.getEndereco());
        r.setTelefone(a.getTelefone());
        r.setMercado(a.getMercado());
        r.setCategoria(a.getCategoria());
        r.setFuncionarios(a.getFuncionarios());
        r.setPagamento(a.getPagamento());
        r.setAtivo(a.getAtivo());
        r.setCriadoEm(a.getCriadoEm());
        return r;
    }
}
